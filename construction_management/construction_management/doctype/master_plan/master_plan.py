# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from bisect import bisect_left
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cint,
	date_diff,
	flt,
	get_first_day,
	get_last_day,
	getdate,
)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_TYPES = ["Sunday", "Holiday", "Rainy Day", "Holiday Leave"]

MONTH_LABELS = [
	"Jan",
	"Feb",
	"Mar",
	"Apr",
	"May",
	"Jun",
	"Jul",
	"Aug",
	"Sep",
	"Oct",
	"Nov",
	"Dec",
]


def _ordinal(number):
	"""1 -> 1st, 2 -> 2nd, 11 -> 11th, 21 -> 21st ..."""
	n = cint(number)
	if 10 <= n % 100 <= 20:
		suffix = "th"
	else:
		suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
	return f"{n}{suffix}"


class MasterPlan(Document):
	pass


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_project_tasks(project):
	"""Return the leaf tasks of a project with the fields needed to build WBS rows."""
	if not project:
		return []

	return frappe.get_all(
		"Task",
		filters={"project": project, "status": ["!=", "Cancelled"], "is_group": 0},
		fields=[
			"name",
			"subject",
			"custom_unit",
			"custom_contract_qty",
			"custom_unit_rate",
			"custom_contract_amount",
			"duration",
			"exp_start_date",
			"exp_end_date",
			"custom_todate_exexuted_qty",
			"task_duration_in_hour",
			"task_duration_in_days",
			"working_hour_per_day",
			"cost_break_down",
		],
		order_by="creation asc",
		limit_page_length=0,
	)


# ---------------------------------------------------------------------------
# Holiday / working day engine (standard ERPNext Holiday List)
# ---------------------------------------------------------------------------
def _to_country_code(country):
	"""Normalise a country name / code to its ISO alpha-2 code (e.g. Ethiopia -> ET).

	Holiday Lists on this site store the ISO code ("ET") while the Company stores
	the full name ("Ethiopia"), so both must resolve to the same value to find the
	right Holiday List(s).
	"""
	if not country:
		return None
	country = str(country).strip()
	if not country:
		return None
	if len(country) == 2:
		return country.upper()

	code = frappe.db.get_value("Country", {"name": country}, "code")
	if code:
		return code.upper()
	code = frappe.db.get_value("Country", {"code": country.upper()}, "code")
	if code:
		return code.upper()
	return country


def _country_names(country):
	"""Return the set of values a Holiday List.country could hold for this country."""
	code = _to_country_code(country)
	if not code:
		return set()
	names = {code}
	name = frappe.db.get_value("Country", {"code": code}, "name")
	if name:
		names.add(name)
	return names


def _default_company_country():
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if company:
		return _to_country_code(frappe.db.get_value("Company", company, "country"))
	return None


def _resolve_country(holiday_list=None, country=None):
	if holiday_list:
		list_country = frappe.db.get_value("Holiday List", holiday_list, "country")
		if list_country:
			return _to_country_code(list_country)
	if country:
		return _to_country_code(country)
	# Default to Ethiopia when nothing is set (this deployment is ET).
	return _default_company_country() or "ET"


def _overlapping_holiday_lists(country, start_date, end_date, holiday_list=None):
	"""Holiday Lists that overlap the project window, optionally filtered by country."""
	if holiday_list:
		return [holiday_list]

	filters = {"from_date": ["<=", end_date], "to_date": [">=", start_date]}
	names = _country_names(country)
	if names:
		filters["country"] = ["in", list(names)]
	return frappe.get_all("Holiday List", filters=filters, pluck="name")


def _weekly_off_date_set(weekly_offs, start_date, end_date):
	"""All dates in the window that are weekly offs (e.g. every Sunday)."""
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	weekly_offs = weekly_offs or {"Sunday"}
	idx_set = {WEEKDAYS.index(w) for w in weekly_offs if w in WEEKDAYS} or {6}
	dates = set()
	d = start_date
	while d <= end_date:
		if d.weekday() in idx_set:
			dates.add(d)
		d = add_days(d, 1)
	return dates


def _collect_holiday_dates(country, start_date, end_date, holiday_list=None):
	"""Return (holiday_dates, weekly_off_dates, rows, weekly_offs).

	Holidays are read from the standard ERPNext Holiday List(s); weekly offs are
	kept separate so the matrix can show Holidays and Sundays independently.
	"""
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	names = _overlapping_holiday_lists(country, start_date, end_date, holiday_list)

	holiday_dates = set()
	weekly_off_dates = set()
	rows = []
	weekly_offs = set()

	if names:
		for hl in frappe.get_all(
			"Holiday List", filters={"name": ["in", names]}, fields=["name", "weekly_off"]
		):
			if hl.weekly_off:
				weekly_offs.add(hl.weekly_off)

		for h in frappe.get_all(
			"Holiday",
			filters={"parent": ["in", names], "holiday_date": ["between", [start_date, end_date]]},
			fields=["holiday_date", "description", "weekly_off"],
			order_by="holiday_date asc",
		):
			d = getdate(h.holiday_date)
			if cint(h.weekly_off):
				weekly_off_dates.add(d)
				continue
			holiday_dates.add(d)
			rows.append(
				{
					"holiday_date": d,
					"description": h.description or _("Holiday"),
					"weekly_off": 0,
				}
			)
	elif country:
		# No Holiday List yet: build from the same country holiday library ERPNext uses.
		try:
			from holidays import country_holidays

			for holiday_date, holiday_name in country_holidays(
				country, years=list(range(start_date.year, end_date.year + 1))
			).items():
				if start_date <= holiday_date <= end_date:
					holiday_dates.add(holiday_date)
					rows.append(
						{"holiday_date": holiday_date, "description": holiday_name, "weekly_off": 0}
					)
		except Exception:
			frappe.log_error(title="Master Plan: country holiday lookup failed")

	if not weekly_offs:
		weekly_offs.add("Sunday")
	weekly_off_dates |= _weekly_off_date_set(weekly_offs, start_date, end_date)

	rows.sort(key=lambda r: r["holiday_date"])
	return holiday_dates, weekly_off_dates, rows, weekly_offs


def _classify_rows(holiday_rows):
	"""Expand the editable grid rows into non-working date sets grouped by Type."""
	buckets = {t: set() for t in DAY_TYPES}
	for h in holiday_rows or []:
		from_date = h.get("from_date")
		if not from_date:
			continue
		day_type = (h.get("day_type") or "Holiday").strip()
		if day_type not in buckets:
			day_type = "Holiday"
		d = getdate(from_date)
		end = getdate(h.get("to_date") or from_date)
		if end < d:
			d, end = end, d
		while d <= end:
			buckets[day_type].add(d)
			d = add_days(d, 1)
	return buckets


def _non_working_date_set(holiday_rows):
	"""Union of every non-working grid row (used by the distribution)."""
	buckets = _classify_rows(holiday_rows)
	non_working = set()
	for t in DAY_TYPES:
		non_working |= buckets[t]
	return non_working


def _count_working_days(seg_start, seg_end, holiday_dates):
	seg_start = getdate(seg_start)
	seg_end = getdate(seg_end)
	if seg_start > seg_end:
		return 0

	total = 0
	d = seg_start
	while d <= seg_end:
		if d not in holiday_dates:
			total += 1
		d = add_days(d, 1)
	return total


def _months_between(start_date, end_date):
	"""List of (first_day, last_day) month tuples covering the window."""
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	months = []
	cursor = get_first_day(start_date)
	while cursor <= end_date:
		months.append((get_first_day(cursor), get_last_day(cursor)))
		cursor = add_days(get_last_day(cursor), 1)
	return months


def _fiscal_year_rows(months):
	"""Group monthly working days into Ethiopian fiscal years (Jul -> Jun)."""
	rows = {}
	for m in months:
		fy = m["year"] if m["month"] >= 7 else m["year"] - 1
		if fy not in rows:
			rows[fy] = {"year": str(fy), **{str(i): 0 for i in range(1, 13)}}
		rows[fy][str(m["month"])] = m["working_days"]
	return [rows[fy] for fy in sorted(rows)]


def _stat_card(label, value, color="#0f172a"):
	return (
		"<div style='flex:1 1 120px;min-width:120px;border:1px solid #e2e8f0;border-radius:10px;"
		"padding:10px 12px;background:#ffffff'>"
		f"<div style='font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.03em'>{label}</div>"
		f"<div style='font-size:22px;font-weight:700;color:{color}'>{value}</div>"
		"</div>"
	)


CELL_H = "padding:5px 6px;border:1px solid #e2e8f0;background:#f1f5f9;font-weight:600;text-align:center;"
CELL_T = "padding:5px 6px;border:1px solid #eef2f7;"


def _availability_matrix_html(data):
	matrix = data.get("availability_matrix") or []
	col_totals = data.get("availability_month_totals") or [0] * 12
	if not matrix:
		return ""

	max_val = max([v for r in matrix for v in r["months"]] or [0]) or 1

	head = "".join(f"<th style='{CELL_H}'>{m}</th>" for m in MONTH_LABELS)
	body = ""
	for r in matrix:
		cells = ""
		for val in r["months"]:
			if not val:
				cells += f"<td style='{CELL_T}text-align:right;color:#cbd5e1'>-</td>"
			else:
				ratio = val / max_val
				alpha = 0.05 + ratio * 0.55
				color = "#ffffff" if ratio > 0.6 else "#1f2937"
				cells += (
					f"<td style='{CELL_T}text-align:right;background:rgba(37,99,235,{alpha:.3f});"
					f"color:{color}'>{val}</td>"
				)
		body += (
			f"<tr><td style='{CELL_T}font-weight:600'>{r['year']}</td>{cells}"
			f"<td style='{CELL_T}text-align:right;font-weight:700'>{r['total']}</td></tr>"
		)

	foot_cells = "".join(f"<td style='{CELL_T}text-align:right;font-weight:600'>{v or ''}</td>" for v in col_totals)
	foot = (
		f"<tr><td style='{CELL_T}font-weight:700'>{_('Total')}</td>{foot_cells}"
		f"<td style='{CELL_T}text-align:right;font-weight:700'>"
		f"{sum(r['total'] for r in matrix)}</td></tr>"
	)

	return (
		f"<div style='padding:4px 12px 0'><b style='font-size:13px'>{_('Available (Working) Days per Month')}</b></div>"
		"<div style='padding:6px 12px 12px;overflow:auto'>"
		"<table style='width:100%;border-collapse:collapse;font-size:12px'>"
		f"<thead><tr><th style='{CELL_H};text-align:left'>{_('Year')}</th>{head}"
		f"<th style='{CELL_H}'>{_('Total')}</th></tr></thead>"
		f"<tbody>{body}</tbody><tfoot>{foot}</tfoot></table></div>"
	)


def _calendar_html(data):
	country = data.get("country") or "-"
	weekly_offs = data.get("weekly_offs") or ["Sunday"]
	off = ", ".join(weekly_offs) if isinstance(weekly_offs, (list, tuple, set)) else str(weekly_offs)

	stats = (
		"<div style='display:flex;flex-wrap:wrap;gap:8px;padding:10px 12px'>"
		+ _stat_card(_("Calendar Days"), data.get("total_calendar_days", 0))
		+ _stat_card(_("Available (Working) Days"), data.get("total_working_days", 0), "#0a7d33")
		+ _stat_card(_("Sundays"), data.get("total_weekly_offs", 0), "#b45309")
		+ _stat_card(_("Holidays"), data.get("total_holidays", 0), "#b91c1c")
		+ _stat_card(_("Expected Rainy Days"), data.get("total_rainy_days", 0), "#0369a1")
		+ _stat_card(_("Holiday Leave Days"), data.get("total_holiday_leave_days", 0), "#7c3aed")
		+ "</div>"
	)

	return (
		"<div style='border:1px solid var(--border-color,#e2e8f0);border-radius:10px;"
		"overflow:hidden;margin:4px 0'>"
		"<div style='padding:10px 14px;background:var(--subtle-fg,#f8fafc);"
		"border-bottom:1px solid var(--border-color,#e2e8f0)'>"
		f"<b>{_('Working Days Calendar')}</b> &middot; {country} &middot; "
		f"{_('Weekly Off')}: {off} &middot; {data.get('start_date')} &rarr; {data.get('end_date')}"
		"</div>"
		f"{stats}"
		f"{_availability_matrix_html(data)}"
		"</div>"
	)


def _build_calendar(
	start_date,
	end_date,
	weekly_offs,
	weekly_off_dates,
	typed,
	country,
	season_length_months=6,
):
	"""Build the month wise calendar shown in the (read only) Excel style matrix.

	``typed`` is a ``{Type: set(dates)}`` map built from the editable grid rows
	(Sunday / Holiday / Rainy Day / Holiday Leave). ``weekly_off_dates`` holds the
	automatic weekly offs. A day counts once, in this priority order:
	Sunday > Holiday > Rainy Day > Holiday Leave.
	"""
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	weekly_offs = weekly_offs or {"Sunday"}
	season_length_months = max(1, cint(season_length_months) or 6)

	typed = typed or {}
	sun_set = set(weekly_off_dates or set()) | set(typed.get("Sunday", set()))
	hol_set = set(typed.get("Holiday", set())) - sun_set
	rain_set = set(typed.get("Rainy Day", set()))
	leave_set = set(typed.get("Holiday Leave", set()))

	months = []
	totals = {
		"calendar_days": 0,
		"rainy_days": 0,
		"holidays": 0,
		"holiday_leave_days": 0,
		"sundays": 0,
		"working_days": 0,
	}
	for i, (ps, pe) in enumerate(_months_between(start_date, end_date)):
		seg_s = max(ps, start_date)
		seg_e = min(pe, end_date)
		cal = date_diff(seg_e, seg_s) + 1

		sundays = 0
		holidays = 0
		rainy = 0
		leave = 0
		day_numbers = []
		cursor = seg_s
		while cursor <= seg_e:
			if cursor in sun_set:
				sundays += 1
			elif cursor in hol_set:
				holidays += 1
			elif cursor in rain_set:
				rainy += 1
			elif cursor in leave_set:
				leave += 1
			else:
				day_numbers.append(cursor.day)
			cursor = add_days(cursor, 1)

		wd = len(day_numbers)

		months.append(
			{
				"key": ps.strftime("%Y-%m"),
				"year": ps.year,
				"month": ps.month,
				"month_name": MONTH_LABELS[ps.month - 1],
				"label": f"{MONTH_LABELS[ps.month - 1]},{ps.year}",
				"season": _("Season {0}").format(i // season_length_months + 1),
				"period_start": str(seg_s),
				"period_end": str(seg_e),
				"calendar_days": cal,
				"rainy_days": rainy,
				"holidays": holidays,
				"holiday_leave_days": leave,
				"sundays": sundays,
				"working_days": wd,
				"days": day_numbers,
			}
		)
		totals["calendar_days"] += cal
		totals["rainy_days"] += rainy
		totals["holidays"] += holidays
		totals["holiday_leave_days"] += leave
		totals["sundays"] += sundays
		totals["working_days"] += wd

	weekly_off_days = sorted(weekly_offs)

	# Year x month matrix of available (working) days.
	matrix_map = {}
	for m in months:
		matrix_map.setdefault(m["year"], {})[m["month"]] = m["working_days"]
	availability = []
	for y in sorted(matrix_map):
		row = [matrix_map[y].get(i, 0) for i in range(1, 13)]
		availability.append({"year": str(y), "months": row, "total": sum(row)})
	col_totals = [sum(a["months"][i] for a in availability) for i in range(12)]

	data = {
		"country": country,
		"weekly_offs": weekly_off_days,
		"weekly_off": weekly_off_days[0]
		if len(weekly_off_days) == 1
		else ", ".join(weekly_off_days),
		"start_date": str(start_date),
		"end_date": str(end_date),
		"season_length_months": season_length_months,
		"total_calendar_days": totals["calendar_days"],
		"total_working_days": totals["working_days"],
		"total_rainy_days": totals["rainy_days"],
		"total_holidays": totals["holidays"],
		"total_holiday_leave_days": totals["holiday_leave_days"],
		"total_weekly_offs": totals["sundays"],
		"total_non_working_days": totals["calendar_days"] - totals["working_days"],
		"totals": totals,
		"months": months,
		"working_days_rows": _fiscal_year_rows(months),
		"availability_matrix": availability,
		"availability_month_totals": col_totals,
	}
	data["html"] = _calendar_html(data)
	return data


@frappe.whitelist()
def get_working_calendar(
	holiday_list=None,
	country=None,
	start_date=None,
	end_date=None,
	season_length_months=6,
):
	"""Seed the holiday rows + month wise working days for the project window.

	Holidays come from the standard ERPNext Holiday List (Ethiopian / ET by default).
	The returned rows fill the editable grid so users can add or avoid days.
	"""
	if not start_date or not end_date:
		frappe.throw(_("Please set the Project Start Date and Project End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if start_date > end_date:
		frappe.throw(_("Project Start Date cannot be after Project End Date."))

	country = _resolve_country(holiday_list, country)
	holiday_dates, weekly_off_dates, holiday_rows, weekly_offs = _collect_holiday_dates(
		country, start_date, end_date, holiday_list
	)

	typed = {t: set() for t in DAY_TYPES}
	typed["Holiday"] = holiday_dates
	typed["Sunday"] = weekly_off_dates

	data = _build_calendar(
		start_date,
		end_date,
		weekly_offs,
		weekly_off_dates,
		typed,
		country,
		season_length_months=season_length_months,
	)
	off_label = ", ".join(sorted(weekly_offs)) or "Sunday"
	seeded = [
		{
			"day_type": "Holiday",
			"holiday_name": r["description"],
			"from_date": str(r["holiday_date"]),
			"to_date": str(r["holiday_date"]),
			"total": 1,
			"month": r["holiday_date"].month,
		}
		for r in holiday_rows
	] + [
		{
			"day_type": "Sunday",
			"holiday_name": _("Weekly Off ({0})").format(off_label),
			"from_date": str(d),
			"to_date": str(d),
			"total": 1,
			"month": d.month,
		}
		for d in sorted(weekly_off_dates)
	]
	seeded.sort(key=lambda r: r["from_date"])
	data["holidays"] = seeded
	return data


@frappe.whitelist()
def recompute_working_days(
	holidays=None,
	country=None,
	weekly_off=None,
	start_date=None,
	end_date=None,
	season_length_months=6,
):
	"""Recompute working days from the current (possibly hand edited) grid."""
	if not start_date or not end_date:
		frappe.throw(_("Please set the Project Start Date and Project End Date first."))

	holiday_rows = frappe.parse_json(holidays) if isinstance(holidays, str) else (holidays or [])
	weekly_offs = {w.strip() for w in (weekly_off or "").split(",") if w.strip()} or {"Sunday"}
	typed = _classify_rows(holiday_rows)
	weekly_off_dates = typed["Sunday"]
	country = country or _default_company_country() or "ET"
	return _build_calendar(
		start_date,
		end_date,
		weekly_offs,
		weekly_off_dates,
		typed,
		country,
		season_length_months=season_length_months,
	)


@frappe.whitelist()
def get_monthly_distribution(
	holiday_list=None,
	country=None,
	holidays=None,
	start_date=None,
	end_date=None,
	tasks=None,
	season_length_months=6,
	weekly_off=None,
	overrides=None,
):
	"""Spread each task quantity across the project months proportionally to working days.

	Returns a compact matrix (columns = months, rows = tasks with a per month cell map)
	so the whole plan can be shown as one Excel style table instead of thousands of rows.

	``overrides`` holds hand edited cells (task_id, month, qty). Any month present there
	keeps the typed value instead of the working day weighted split.
	"""
	if not start_date or not end_date:
		frappe.throw(_("Please set the Project Start Date and Project End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	tasks = frappe.parse_json(tasks) if isinstance(tasks, str) else (tasks or [])
	overrides = frappe.parse_json(overrides) if isinstance(overrides, str) else (overrides or [])
	season_length_months = max(1, cint(season_length_months) or 6)
	weekly_offs = {w.strip() for w in (weekly_off or "").split(",") if w.strip()} or {"Sunday"}

	overrides_map = {}
	for o in overrides:
		tid, mon = o.get("task_id"), o.get("month")
		if tid and mon and o.get("qty") is not None and o.get("qty") != "":
			overrides_map[(tid, mon)] = flt(o.get("qty"))

	holiday_rows = frappe.parse_json(holidays) if isinstance(holidays, str) else holidays
	if holiday_rows:
		holiday_dates = _non_working_date_set(holiday_rows)
	else:
		country = _resolve_country(holiday_list, country)
		hd, wod, _rows, _wo = _collect_holiday_dates(country, start_date, end_date, holiday_list)
		holiday_dates = hd | wod

	project_months = _months_between(start_date, end_date)

	columns = []
	for i, (ps, pe) in enumerate(project_months):
		seg_start = max(ps, start_date)
		seg_end = min(pe, end_date)
		season_no = i // season_length_months + 1
		columns.append(
			{
				"key": ps.strftime("%Y-%m"),
				"label": f"{MONTH_LABELS[ps.month - 1]},{ps.year}",
				"month_index": i + 1,
				"season": _("{0} Season").format(_ordinal(season_no)),
				"season_index": season_no,
				"working_days": _count_working_days(seg_start, seg_end, holiday_dates),
			}
		)

	rows = []
	for task in tasks:
		t_start = task.get("start_date")
		t_end = task.get("finish_date") or task.get("end_date")
		if not t_start or not t_end:
			continue

		interval_start = max(getdate(t_start), start_date)
		interval_end = min(getdate(t_end), end_date)
		if interval_start > interval_end:
			continue

		task_months = _months_between(interval_start, interval_end)
		working = [
			_count_working_days(max(ps, interval_start), min(pe, interval_end), holiday_dates)
			for ps, pe in task_months
		]

		total_wd = sum(working)
		if total_wd <= 0:
			continue

		qty = flt(task.get("contract_qty"))
		rate = flt(task.get("task_unit_rate"))
		task_id = task.get("task_id")
		last_idx = max(i for i, w in enumerate(working) if w > 0)
		allocated = 0.0

		cells = {}
		distributed = 0.0
		has_manual = False
		for i, (ps, pe) in enumerate(task_months):
			month_key = ps.strftime("%Y-%m")
			override = overrides_map.get((task_id, month_key))
			manual = override is not None
			if manual:
				planned = round(override, 4)
				percent = round(planned * 100.0 / qty, 2) if qty else 0.0
				has_manual = True
			elif i == last_idx:
				# Absorb the rounding drift so the row sums back to the contract qty.
				planned = round(qty - allocated, 4)
				percent = round(working[i] * 100.0 / total_wd, 2)
			else:
				planned = round(qty * working[i] / total_wd, 4)
				percent = round(working[i] * 100.0 / total_wd, 2)

			# Accumulate the FINAL planned value (override aware) so a manual month
			# adjusts the pool left for the remaining months.
			allocated += planned
			distributed += planned
			cells[month_key] = {
				"qty": planned,
				"amount": round(planned * rate, 2),
				"percent": percent,
				"working_days": working[i],
				"manual": manual,
			}

		rows.append(
			{
				"task_id": task_id,
				"task_name": task.get("task_name"),
				"series": task.get("series"),
				"uom": task.get("uom"),
				"contract_qty": qty,
				"unit_rate": rate,
				"total_planned_qty": qty,
				"distributed_qty": round(distributed, 4),
				"has_manual": has_manual,
				"total_planned_amount": round(qty * rate, 2),
				"total_working_days": total_wd,
				"cells": cells,
			}
		)

	return {"columns": columns, "rows": rows, "season_length_months": season_length_months}


# ---------------------------------------------------------------------------
# Activity sequencing + Critical Path Method (working day based)
# ---------------------------------------------------------------------------
REL_TYPES = ("Finish to Start", "Start to Start", "Finish to Finish", "Start to Finish")


def _working_day_axis(start_date, end_date, non_working):
	"""Ordered list of working dates between start and end (inclusive)."""
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	days = []
	d = start_date
	while d <= end_date:
		if d not in non_working:
			days.append(d)
		d = add_days(d, 1)
	return days


def _snap_forward(axis, date):
	"""Index of the first working day on/after ``date`` (clamped to the axis)."""
	if not axis:
		return 0
	i = bisect_left(axis, getdate(date))
	if i >= len(axis):
		return len(axis) - 1
	return i


def _snap_backward(axis, date):
	"""Index of the last working day on/before ``date`` (clamped to the axis)."""
	if not axis:
		return 0
	i = bisect_left(axis, getdate(date))
	if i >= len(axis):
		return len(axis) - 1
	if axis[i] == getdate(date):
		return i
	return max(0, i - 1)


def _duration_days(value):
	"""Round a task duration (in days) up to a whole number of working days."""
	v = flt(value)
	if v <= 0:
		return 0
	whole = int(v)
	if v > whole:
		whole += 1
	return max(whole, 1)


def _topo_order(nodes, succ, pred):
	"""Kahn topological sort; falls back to the given order on a cycle."""
	order = list(nodes.keys())
	indeg = {n: len(pred.get(n, [])) for n in order}
	queue = [n for n in order if indeg[n] == 0]
	result = []
	while queue:
		n = queue.pop(0)
		result.append(n)
		for edge in succ.get(n, []):
			s = edge[0]
			indeg[s] -= 1
			if indeg[s] == 0:
				queue.append(s)
	if len(result) != len(order):
		# Cycle detected: keep the original order so the user still gets dates.
		return order
	return result


def _run_cpm(axis, start_idx, end_idx, nodes, edges):
	"""Forward/backward pass. ``nodes`` maps task -> duration (working days);
	``edges`` is a list of ``(predecessor, successor, relationship, lag, lead)``.

	Returns ``{task: {es, ef, ls, lf, free_float, total_float, is_critical}}``
	where all start/finish values are indexes into ``axis``.
	"""
	succ = {n: [] for n in nodes}
	pred = {n: [] for n in nodes}
	for p, s, rel, lag, lead in edges:
		if p not in nodes or s not in nodes or p == s:
			continue
		rel = rel if rel in REL_TYPES else "Finish to Start"
		succ[p].append((s, rel, flt(lag), flt(lead)))
		pred[s].append((p, rel, flt(lag), flt(lead)))

	order = _topo_order(nodes, succ, pred)
	es, ef, ls, lf = {}, {}, {}, {}
	last = max(len(axis) - 1, 0)

	# Forward pass -> earliest start / finish.
	for n in order:
		dur = nodes[n]
		span = max(cint(dur) - 1, 0)
		if not pred[n]:
			es[n] = start_idx
		else:
			best = start_idx
			for p, rel, lag, lead in pred[n]:
				offset = lag - lead
				if rel == "Start to Start":
					cand = es[p] + offset
				elif rel == "Finish to Finish":
					cand = ef[p] + offset - span
				elif rel == "Start to Finish":
					cand = es[p] + offset - span
				else:  # Finish to Start
					cand = ef[p] + 1 + offset
				best = max(best, cand)
			es[n] = best
		es[n] = int(min(max(round(es[n]), 0), last))
		ef[n] = int(min(es[n] + span, last))

	# The longest path ends at the earliest possible project finish, so the
	# critical path is meaningful even when the deadline has slack.
	finish_idx = max(ef.values()) if ef else end_idx

	# Backward pass -> latest start / finish.
	for n in reversed(order):
		dur = nodes[n]
		span = max(cint(dur) - 1, 0)
		if not succ[n]:
			lf[n] = finish_idx
		else:
			best = last
			for s, rel, lag, lead in succ[n]:
				offset = lag - lead
				if rel == "Start to Start":
					cand = ls[s] - offset + span
				elif rel == "Finish to Finish":
					cand = lf[s] - offset
				elif rel == "Start to Finish":
					cand = lf[s] - offset + span
				else:  # Finish to Start
					cand = ls[s] - 1 - offset
				best = min(best, cand)
			lf[n] = best
		lf[n] = int(min(max(round(lf[n]), 0), last))
		ls[n] = int(max(lf[n] - span, 0))

	result = {}
	for n in nodes:
		total_float = ls[n] - es[n]
		free_float = 0
		if succ[n]:
			free_float = min(es[s] for s, _r, _l, _ld in succ[n]) - ef[n] - 1
			free_float = max(free_float, 0)
		result[n] = {
			"es": es[n],
			"ef": ef[n],
			"ls": ls[n],
			"lf": lf[n],
			"free_float": free_float,
			"total_float": total_float,
			"is_critical": total_float <= 0,
		}
	return result


@frappe.whitelist()
def compute_schedule(
	project=None,
	start_date=None,
	end_date=None,
	holidays=None,
	tasks=None,
	sequencing=None,
	weekly_off=None,
	start_date_of_first_task=None,
	write_back=0,
):
	"""Sequence the project tasks with the CPM and return start/finish dates.

	``tasks`` is the WBS list (``task_id`` + ``duration`` in days); ``sequencing``
	is the Activity Sequencing grid (predecessor -> activity). When no sequencing
	is supplied a Finish-to-Start chain is built in WBS order so every task gets a
	real start/finish window instead of the whole project period.
	"""
	if not start_date or not end_date:
		frappe.throw(_("Please set the Project Start Date and Project End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if start_date > end_date:
		frappe.throw(_("Project Start Date cannot be after Project End Date."))

	tasks = frappe.parse_json(tasks) if isinstance(tasks, str) else (tasks or [])
	sequencing = frappe.parse_json(sequencing) if isinstance(sequencing, str) else (sequencing or [])
	holiday_rows = frappe.parse_json(holidays) if isinstance(holidays, str) else (holidays or [])
	non_working = _non_working_date_set(holiday_rows)

	axis = _working_day_axis(start_date, end_date, non_working)
	if not axis:
		frappe.throw(_("No working days found in the selected project period."))

	nodes = {}
	task_meta = {}
	for task in tasks:
		tid = task.get("task_id")
		if not tid or tid in nodes:
			continue
		dur = _duration_days(task.get("duration") or task.get("task_duration_in_days"))
		nodes[tid] = max(dur, 1)
		task_meta[tid] = task

	if not nodes:
		return {"rows": [], "critical_path": [], "critical_path_duration_in_day": 0}

	edges = []
	for row in sequencing:
		pred = row.get("predecessor_activity")
		succ_task = row.get("activity")
		if pred and succ_task:
			edges.append(
				(
					pred,
					succ_task,
					row.get("relationship_type") or "Finish to Start",
					row.get("lag_days") or 0,
					row.get("lead_days") or 0,
				)
			)

	# No explicit relationships -> default chain in WBS order.
	if not edges:
		ordered = list(nodes.keys())
		for i in range(1, len(ordered)):
			edges.append((ordered[i - 1], ordered[i], "Finish to Start", 0, 0))

	start_idx = _snap_forward(axis, getdate(start_date_of_first_task or start_date))
	end_idx = _snap_backward(axis, end_date)

	cpm = _run_cpm(axis, start_idx, end_idx, nodes, edges)

	rows = []
	for tid, meta in task_meta.items():
		c = cpm[tid]
		es_date = axis[c["es"]]
		ef_date = axis[c["ef"]]
		rows.append(
			{
				"task_id": tid,
				"task_name": meta.get("task_name"),
				"duration_days": nodes[tid],
				"es": str(es_date),
				"ef": str(ef_date),
				"ls": str(axis[c["ls"]]),
				"lf": str(axis[c["lf"]]),
				"free_float": c["free_float"],
				"total_float": c["total_float"],
				"start_date": str(es_date),
				"finish_date": str(ef_date),
				"is_critical": 1 if c["is_critical"] else 0,
			}
		)

	critical_path = [r for r in sorted(rows, key=lambda r: (r["es"], r["ef"])) if r["is_critical"]]
	critical_duration = 0
	if rows:
		critical_duration = axis.index(getdate(critical_path[-1]["finish_date"])) - start_idx + 1 if critical_path else 0
	critical_duration = max(critical_duration, 0)

	if cint(write_back):
		for r in rows:
			frappe.db.set_value(
				"Task",
				r["task_id"],
				{"exp_start_date": r["start_date"], "exp_end_date": r["finish_date"]},
				update_modified=False,
			)

	return {
		"rows": rows,
		"critical_path": [r["task_id"] for r in critical_path],
		"critical_path_names": [r["task_name"] or r["task_id"] for r in critical_path],
		"critical_path_duration_in_day": critical_duration,
		"start_date": str(start_date),
		"end_date": str(end_date),
		"working_days": len(axis),
	}


@frappe.whitelist()
def get_task_resources(project=None, tasks=None):
	"""Explode each task's Cost Break Down into the resource scheduling tables.

	Returns ``{machinery, manpower, material}`` lists ready to fill the
	Task * Scheduling child tables on the Master Plan.
	"""
	tasks = frappe.parse_json(tasks) if isinstance(tasks, str) else (tasks or [])
	machinery, manpower, material = [], [], []

	for task in tasks:
		tid = task.get("task_id")
		if not tid:
			continue
		info = frappe.db.get_value(
			"Task",
			tid,
			["name", "subject", "cost_break_down", "task_duration_in_hour", "working_hour_per_day"],
			as_dict=True,
		)
		if not info or not info.cost_break_down:
			continue

		start = task.get("start_date")
		end = task.get("finish_date")
		year = (start or "")[:4]
		dur_hours = flt(info.task_duration_in_hour)
		working_hour = flt(info.working_hour_per_day) or 8

		cbd = frappe.get_doc("Cost Break Down", info.cost_break_down)

		for m in cbd.machineries:
			qty = flt(m.no)
			hourly = flt(m.hourly_cost)
			machinery.append(
				{
					"year": year,
					"task_id": tid,
					"task_name": info.subject,
					"type": m.type,
					"qty": qty,
					"task_duration_in_hour": dur_hours,
					"working_hour": working_hour,
					"rental_rate": flt(m.hourly_rental),
					"total_hourly_cost": hourly,
					"total_cost": round(qty * dur_hours * hourly, 2),
					"start_date": start,
					"end_date": end,
				}
			)

		for m in cbd.manpowers:
			qty = flt(m.no)
			hourly = flt(m.hourly_cost)
			manpower.append(
				{
					"year": year,
					"task_id": tid,
					"task_name": info.subject,
					"job_title": m.labour,
					"qty": qty,
					"uf": flt(m.uf) or 1,
					"task_duration_in_hour": dur_hours,
					"working_hour": working_hour,
					"rental_rate": flt(m.indexed_hourly_cost),
					"total_hourly_cost": hourly,
					"total_cost": round(qty * dur_hours * hourly, 2),
					"start_date": start,
					"end_date": end,
				}
			)

		for m in cbd.materials:
			qty = flt(m.qty)
			rate = flt(m.rate)
			material.append(
				{
					"year": year,
					"task_id": tid,
					"task_name": info.subject,
					"item1": m.item,
					"uom": m.unit,
					"qty": qty,
					"working_hour": working_hour,
					"unit_rate": rate,
					"total_cost": round(qty * rate, 2),
					"start_date": start,
					"end_date": end,
				}
			)

	return {"machinery": machinery, "manpower": manpower, "material": material}

