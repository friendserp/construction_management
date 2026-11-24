# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

from bisect import bisect_left
from math import ceil

import frappe
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
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
REL_TYPES = ("Finish to Start", "Start to Start", "Finish to Finish", "Start to Finish")


def _ordinal(number):
	n = cint(number)
	if 10 <= n % 100 <= 20:
		suffix = "th"
	else:
		suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
	return f"{n}{suffix}"


class MasterPlan(Document):
	def validate(self):
		self._validate_distribution_qty()

	def _validate_distribution_qty(self):
		if not self.wbs or not self.distribution:
			return
		contract, names = {}, {}
		for row in self.wbs:
			if not row.task_id:
				continue
			contract[row.task_id] = flt(row.contract_qty)
			names[row.task_id] = row.task_name or row.task_id

		totals = {}
		for row in self.distribution:
			if not row.task_id or not row.month:
				continue
			totals[row.task_id] = totals.get(row.task_id, 0.0) + flt(row.qty)

		for task_id, total in totals.items():
			qty = contract.get(task_id)
			if qty and total > qty + 1e-9:
				frappe.throw(
					_("Task {0}: distributed qty {1} exceeds the total qty {2}.").format(
						names.get(task_id, task_id), total, qty
					)
				)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_project_tasks(project):
	if not project:
		return []
	return frappe.get_all(
		"Task",
		filters={"project": project, "status": ["!=", "Cancelled"], "is_group": 0},
		fields=[
			"name", "subject", "custom_unit", "custom_contract_qty",
			"custom_unit_rate", "custom_contract_amount", "duration",
			"exp_start_date", "exp_end_date", "custom_todate_exexuted_qty",
			"task_duration_in_days",
		],
		order_by="creation asc",
		limit_page_length=0,
	)


# ---------------------------------------------------------------------------
# Holiday / working day engine
# ---------------------------------------------------------------------------
def _to_country_code(country):
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
	return _default_company_country() or "ET"


def _overlapping_holiday_lists(country, start_date, end_date, holiday_list=None):
	if holiday_list:
		return [holiday_list]
	filters = {"from_date": ["<=", end_date], "to_date": [">=", start_date]}
	names = _country_names(country)
	if names:
		filters["country"] = ["in", list(names)]
	return frappe.get_all("Holiday List", filters=filters, pluck="name")


def _weekly_off_date_set(weekly_offs, start_date, end_date):
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
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	names = _overlapping_holiday_lists(country, start_date, end_date, holiday_list)

	holiday_dates = set()
	weekly_off_dates = set()
	rows = []
	weekly_offs = set()

	if names:
		for hl in frappe.get_all(
			"Holiday List", filters={"name": ["in", names]},
			fields=["name", "weekly_off"],
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
			rows.append({"holiday_date": d, "description": h.description or _("Holiday"), "weekly_off": 0})
	elif country:
		try:
			from holidays import country_holidays
			for holiday_date, holiday_name in country_holidays(
				country, years=list(range(start_date.year, end_date.year + 1))
			).items():
				if start_date <= holiday_date <= end_date:
					holiday_dates.add(holiday_date)
					rows.append({"holiday_date": holiday_date, "description": holiday_name, "weekly_off": 0})
		except Exception:
			frappe.log_error(title="Master Plan: country holiday lookup failed")

	if not weekly_offs:
		weekly_offs.add("Sunday")
	weekly_off_dates |= _weekly_off_date_set(weekly_offs, start_date, end_date)
	rows.sort(key=lambda r: r["holiday_date"])
	return holiday_dates, weekly_off_dates, rows, weekly_offs


def _classify_rows(holiday_rows):
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
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	months = []
	cursor = get_first_day(start_date)
	while cursor <= end_date:
		months.append((get_first_day(cursor), get_last_day(cursor)))
		cursor = add_days(get_last_day(cursor), 1)
	return months


def _fiscal_year_rows(months):
	rows = {}
	for m in months:
		fy = m["year"] if m["month"] >= 7 else m["year"] - 1
		if fy not in rows:
			rows[fy] = {"year": str(fy), **{str(i): 0 for i in range(1, 13)}}
		rows[fy][str(m["month"])] = m["working_days"]
	return [rows[fy] for fy in sorted(rows)]


def _build_calendar(start_date, end_date, weekly_offs, weekly_off_dates, typed, country,
                    season_length_months=6):
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
	totals = {"calendar_days": 0, "rainy_days": 0, "holidays": 0,
	          "holiday_leave_days": 0, "sundays": 0, "working_days": 0}
	for i, (ps, pe) in enumerate(_months_between(start_date, end_date)):
		seg_s = max(ps, start_date)
		seg_e = min(pe, end_date)
		cal = date_diff(seg_e, seg_s) + 1
		sundays = holidays = rainy = leave = 0
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
		months.append({
			"year": ps.year, "month": ps.month,
			"label": f"{MONTH_LABELS[ps.month - 1]},{ps.year}",
			"season": _("Season {0}").format(i // season_length_months + 1),
			"calendar_days": cal, "rainy_days": rainy, "holidays": holidays,
			"holiday_leave_days": leave, "sundays": sundays, "working_days": wd,
		})
		totals["calendar_days"] += cal
		totals["rainy_days"] += rainy
		totals["holidays"] += holidays
		totals["holiday_leave_days"] += leave
		totals["sundays"] += sundays
		totals["working_days"] += wd

	weekly_off_days = sorted(weekly_offs)
	return {
		"country": country,
		"weekly_off": weekly_off_days[0] if len(weekly_off_days) == 1 else ", ".join(weekly_off_days),
		"start_date": str(start_date),
		"end_date": str(end_date),
		"total_working_days": totals["working_days"],
		"totals": totals,
		"months": months,
		"working_days_rows": _fiscal_year_rows(months),
	}


@frappe.whitelist()
def get_working_calendar(holiday_list=None, country=None, start_date=None, end_date=None,
                         season_length_months=6):
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

	data = _build_calendar(start_date, end_date, weekly_offs, weekly_off_dates, typed, country,
	                       season_length_months=season_length_months)
	off_label = ", ".join(sorted(weekly_offs)) or "Sunday"
	seeded = [
		{"day_type": "Holiday", "holiday_name": r["description"],
		 "from_date": str(r["holiday_date"]), "to_date": str(r["holiday_date"]),
		 "total": 1, "month": r["holiday_date"].month}
		for r in holiday_rows
	] + [
		{"day_type": "Sunday", "holiday_name": _("Weekly Off ({0})").format(off_label),
		 "from_date": str(d), "to_date": str(d), "total": 1, "month": d.month}
		for d in sorted(weekly_off_dates)
	]
	seeded.sort(key=lambda r: r["from_date"])
	data["holidays"] = seeded
	return data


@frappe.whitelist()
def recompute_working_days(holidays=None, country=None, weekly_off=None,
                           start_date=None, end_date=None, season_length_months=6):
	if not start_date or not end_date:
		frappe.throw(_("Please set the Project Start Date and Project End Date first."))
	holiday_rows = frappe.parse_json(holidays) if isinstance(holidays, str) else (holidays or [])
	weekly_offs = {w.strip() for w in (weekly_off or "").split(",") if w.strip()} or {"Sunday"}
	typed = _classify_rows(holiday_rows)
	country = country or _default_company_country() or "ET"
	return _build_calendar(start_date, end_date, weekly_offs, typed["Sunday"], typed, country,
	                       season_length_months=season_length_months)


# ---------------------------------------------------------------------------
# Monthly distribution + resource distribution (single round-trip)
# ---------------------------------------------------------------------------
def _distribute_resources(resources, rows_by_task, columns, kind):
	"""Scale each resource by the workload distribution ratio of its task.

	For each month: resource_month_value = resource_total × (month_qty ÷ contract_qty)
	"""
	agg = {}
	for r in resources:
		tid = r.get("task_id")
		dist_row = rows_by_task.get(tid)
		if not dist_row:
			continue
		contract_qty = flt(dist_row["contract_qty"])
		if contract_qty <= 0:
			continue

		if kind == "machinery":
			res_id = r.get("type")
			unit = "No"
			total_qty = flt(r.get("qty"))
			total_hours = 0
			total_cost = flt(r.get("total_cost"))
			metric_key = "qty"
		elif kind == "manpower":
			res_id = r.get("job_title")
			unit = "Person"
			total_qty = 0
			total_hours = flt(r.get("task_duration_in_hour"))
			total_cost = flt(r.get("total_cost"))
			metric_key = "hours"
		else:  # material
			res_id = r.get("item1")
			unit = r.get("uom") or ""
			total_qty = flt(r.get("qty"))
			total_hours = 0
			total_cost = flt(r.get("total_cost"))
			metric_key = "qty"

		if not res_id:
			continue

		if res_id not in agg:
			agg[res_id] = {
				"name": res_id, "unit": unit, "kind": kind,
				"metric_key": metric_key, "cells": {},
			}

		row = agg[res_id]
		for col in columns:
			key = col["key"]
			dist_cell = dist_row["cells"].get(key)
			if not dist_cell:
				continue
			month_qty = flt(dist_cell["qty"])
			ratio = month_qty / contract_qty

			tgt = row["cells"].setdefault(key, {"qty": 0.0, "hours": 0.0, "cost": 0.0})
			tgt["qty"] += total_qty * ratio
			tgt["hours"] += total_hours * ratio
			tgt["cost"] += total_cost * ratio

	result = []
	for name, row in agg.items():
		total_metric = sum(cell[row["metric_key"]] for cell in row["cells"].values())
		total_cost = sum(cell["cost"] for cell in row["cells"].values())
		result.append({
			"name": name,
			"unit": row["unit"],
			"kind": kind,
			"metric_key": row["metric_key"],
			"cells": {
				k: {"qty": round(v["qty"], 4),
				    "hours": round(v["hours"], 2),
				    "cost": round(v["cost"], 2)}
				for k, v in row["cells"].items()
			},
			"total_metric": round(total_metric, 4),
			"total_cost": round(total_cost, 2),
		})
	result.sort(key=lambda r: r["name"] or "")
	return result


@frappe.whitelist()
def get_monthly_distribution(
	holiday_list=None, country=None, holidays=None, start_date=None, end_date=None,
	tasks=None, season_length_months=6, weekly_off=None, overrides=None,
	machinery=None, manpower=None, material=None, auto_distribute=0,
):
	if not start_date or not end_date:
		frappe.throw(_("Please set the Project Start Date and Project End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	tasks = frappe.parse_json(tasks) if isinstance(tasks, str) else (tasks or [])
	overrides = frappe.parse_json(overrides) if isinstance(overrides, str) else (overrides or [])
	machinery = frappe.parse_json(machinery) if isinstance(machinery, str) else (machinery or [])
	manpower = frappe.parse_json(manpower) if isinstance(manpower, str) else (manpower or [])
	material = frappe.parse_json(material) if isinstance(material, str) else (material or [])
	season_length_months = max(1, cint(season_length_months) or 6)
	auto_distribute = cint(auto_distribute)

	overrides_by_task = {}
	for o in overrides:
		tid, mon = o.get("task_id"), o.get("month")
		if tid and mon and o.get("qty") is not None and o.get("qty") != "":
			overrides_by_task.setdefault(tid, {})[mon] = flt(o.get("qty"))

	holiday_rows = frappe.parse_json(holidays) if isinstance(holidays, str) else holidays
	if holiday_rows:
		holiday_dates = _non_working_date_set(holiday_rows)
	else:
		country = _resolve_country(holiday_list, country)
		hd, wod, _rows, _wo = _collect_holiday_dates(country, start_date, end_date, holiday_list)
		holiday_dates = hd | wod
	if weekly_off:
		offs = {w.strip() for w in weekly_off.split(",")} if isinstance(weekly_off, str) else set(weekly_off)
		holiday_dates |= _weekly_off_date_set(offs, start_date, end_date)

	project_months = _months_between(start_date, end_date)

	columns = []
	for i, (ps, pe) in enumerate(project_months):
		seg_start = max(ps, start_date)
		seg_end = min(pe, end_date)
		season_no = i // season_length_months + 1
		columns.append({
			"key": ps.strftime("%Y-%m"),
			"label": f"{MONTH_LABELS[ps.month - 1]},{ps.year}",
			"month_index": i + 1,
			"season": _("{0} Season").format(_ordinal(season_no)),
			"season_index": season_no,
			"working_days": _count_working_days(seg_start, seg_end, holiday_dates),
		})

	rows = []
	for task in tasks:
		t_start = task.get("start_date")
		t_end = task.get("finish_date") or task.get("end_date")
		if not t_start or not t_end:
			continue

		task_id = task.get("task_id")
		interval_start = max(getdate(t_start), start_date)
		interval_end = min(getdate(t_end), end_date)
		if interval_start > interval_end:
			continue

		base_months = _months_between(interval_start, interval_end)
		month_map = {}
		base_keys = set()
		for ps, pe in base_months:
			key = ps.strftime("%Y-%m")
			month_map[key] = (ps, pe)
			base_keys.add(key)

		task_overrides = overrides_by_task.get(task_id, {})
		for key in task_overrides:
			if key in month_map:
				continue
			try:
				ps = get_first_day(getdate(f"{key}-01"))
			except Exception:
				continue
			pe = get_last_day(ps)
			if pe < start_date or ps > end_date:
				continue
			month_map[key] = (ps, pe)

		month_keys = sorted(month_map)
		working = []
		for key in month_keys:
			if key in base_keys:
				ps, pe = month_map[key]
				working.append(_count_working_days(
					max(ps, interval_start), min(pe, interval_end), holiday_dates
				))
			else:
				working.append(0)

		total_wd = sum(working)
		if total_wd <= 0 and not task_overrides:
			continue

		qty = flt(task.get("contract_qty"))
		rate = flt(task.get("task_unit_rate"))

		manual_values = {
			i: round(task_overrides[key], 4)
			for i, key in enumerate(month_keys)
			if key in task_overrides
		}
		manual_total = sum(manual_values.values())
		remaining = 0.0
		auto_indices = []
		auto_wd = 0.0
		last_auto = None
		auto_used = 0.0
		if auto_distribute:
			remaining = max(qty - manual_total, 0.0)
			auto_indices = [i for i in range(len(month_keys))
			                if i not in manual_values and working[i] > 0]
			auto_wd = sum(working[i] for i in auto_indices)
			last_auto = auto_indices[-1] if auto_indices else None

		cells = {}
		distributed = 0.0
		has_manual = bool(manual_values)
		for i, key in enumerate(month_keys):
			if i in manual_values:
				planned = manual_values[i]
				percent = round(planned * 100.0 / qty, 2) if qty else 0.0
			elif not auto_distribute or auto_wd <= 0:
				planned = 0.0
				percent = 0.0
			elif i == last_auto:
				planned = round(remaining - auto_used, 4)
				percent = round(working[i] * 100.0 / total_wd, 2) if total_wd else 0.0
				auto_used += planned
			else:
				planned = round(remaining * working[i] / auto_wd, 4)
				percent = round(working[i] * 100.0 / total_wd, 2) if total_wd else 0.0
				auto_used += planned

			distributed += planned
			cells[key] = {
				"qty": planned, "amount": round(planned * rate, 2),
				"percent": percent, "working_days": working[i],
				"manual": i in manual_values,
			}

		rows.append({
			"task_id": task_id, "task_name": task.get("task_name"),
			"series": task.get("series"), "uom": task.get("uom"),
			"contract_qty": qty, "unit_rate": rate, "total_planned_qty": qty,
			"distributed_qty": round(distributed, 4), "has_manual": has_manual,
			"total_planned_amount": round(qty * rate, 2),
			"total_working_days": total_wd, "cells": cells,
		})

	result = {
		"columns": columns, "rows": rows,
		"season_length_months": season_length_months,
		"auto_distribute": auto_distribute,
	}

	# Resource distribution piggy-backs on the workload distribution
	if machinery or manpower or material:
		rows_by_task = {r["task_id"]: r for r in rows}
		result["machinery"] = _distribute_resources(machinery, rows_by_task, columns, "machinery")
		result["manpower"] = _distribute_resources(manpower, rows_by_task, columns, "manpower")
		result["material"] = _distribute_resources(material, rows_by_task, columns, "material")

	return result


# ---------------------------------------------------------------------------
# Activity sequencing + Critical Path Method
# ---------------------------------------------------------------------------
def _working_day_axis(start_date, end_date, non_working):
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
	if not axis:
		return 0
	i = bisect_left(axis, getdate(date))
	if i >= len(axis):
		return len(axis) - 1
	return i


def _duration_days(value):
	v = flt(value)
	if v <= 0:
		return 0
	whole = int(v)
	if v > whole:
		whole += 1
	return max(whole, 1)


def _topo_order(nodes, succ, pred):
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
		return order
	return result


def _run_cpm(axis, start_idx, nodes, edges):
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
				else:
					cand = ef[p] + 1 + offset
				best = max(best, cand)
			es[n] = best
		es[n] = int(min(max(round(es[n]), 0), last))
		ef[n] = int(min(es[n] + span, last))

	finish_idx = max(ef.values())

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
				else:
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
			"es": es[n], "ef": ef[n], "ls": ls[n], "lf": lf[n],
			"free_float": free_float, "total_float": total_float,
			"is_critical": total_float <= 0,
		}
	return result


@frappe.whitelist()
def compute_schedule(start_date=None, end_date=None, holidays=None, tasks=None,
                     sequencing=None, weekly_off=None, start_date_of_first_task=None,
                     write_back=0):
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

	nodes, task_meta = {}, {}
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
		pred, succ_task = row.get("predecessor_activity"), row.get("activity")
		if pred and succ_task:
			edges.append((pred, succ_task,
			              row.get("relationship_type") or "Finish to Start",
			              row.get("lag_days") or 0, row.get("lead_days") or 0))
	if not edges:
		ordered = list(nodes.keys())
		for i in range(1, len(ordered)):
			edges.append((ordered[i - 1], ordered[i], "Finish to Start", 0, 0))

	start_idx = _snap_forward(axis, getdate(start_date_of_first_task or start_date))
	cpm = _run_cpm(axis, start_idx, nodes, edges)

	rows = []
	for tid, meta in task_meta.items():
		c = cpm[tid]
		es_date, ef_date = axis[c["es"]], axis[c["ef"]]
		rows.append({
			"task_id": tid, "task_name": meta.get("task_name"),
			"duration_days": nodes[tid], "es": str(es_date), "ef": str(ef_date),
			"ls": str(axis[c["ls"]]), "lf": str(axis[c["lf"]]),
			"free_float": c["free_float"], "total_float": c["total_float"],
			"start_date": str(es_date), "finish_date": str(ef_date),
			"is_critical": 1 if c["is_critical"] else 0,
		})

	critical_path = [r for r in sorted(rows, key=lambda r: (r["es"], r["ef"])) if r["is_critical"]]
	critical_duration = 0
	if rows and critical_path:
		critical_duration = axis.index(getdate(critical_path[-1]["finish_date"])) - start_idx + 1
	critical_duration = max(critical_duration, 0)

	if cint(write_back):
		for r in rows:
			frappe.db.set_value(
				"Task", r["task_id"],
				{"exp_start_date": r["start_date"], "exp_end_date": r["finish_date"]},
				update_modified=False,
			)

	return {
		"rows": rows,
		"critical_path": [r["task_id"] for r in critical_path],
		"critical_path_names": [r["task_name"] or r["task_id"] for r in critical_path],
		"critical_path_duration_in_day": critical_duration,
		"start_date": str(start_date), "end_date": str(end_date),
		"working_days": len(axis),
	}


RESOURCE_TABS = (
	"doz", "exc", "grader", "loader", "dt",
	"equipment", "crew", "fuel", "manpower", "material",
)
MACHINE_TABS = ("doz", "exc", "grader", "loader", "dt")

MACHINE_KEYWORDS = {
	"doz": ("dozer", "bulldozer", "d6", "d7", "d8"),
	"exc": ("excav", "backhoe", "hoe"),
	"grader": ("grader",),
	"loader": ("loader",),
	"dt": ("dump", "tipper", "tipper truck", "dump truck"),
}

MACHINE_DEFAULTS = {
	"doz": {"title": "Dozer", "hourly_output": 0.1},
	"exc": {"title": "Excavator", "hourly_output": 20.0},
	"grader": {"title": "Grader", "hourly_output": 80.0},
	"loader": {"title": "Loader", "hourly_output": 140.0},
	"dt": {"title": "Dump Truck", "hourly_output": 15.0},
}

FUEL_RATES = (
	("dozer", 40.0), ("excav", 25.0), ("grader", 15.0), ("roller", 10.0),
	("loader", 13.0), ("backhoe", 10.0), ("dump", 10.0), ("water", 10.0),
	("fuel truck", 10.0), ("drill", 20.0), ("bitumen", 24.0), ("paver", 17.0),
	("pneumatic", 21.0), ("steel drum", 18.0), ("asphalt plant", 110.0),
	("mixer", 2.5), ("compactor", 2.0), ("generator", 15.0),
	("crane", 15.0), ("vehicle", 4.5), ("car", 4.5), ("bus", 6.0),
)


def _json_arg(value, default=None):
	if value is None or value == "":
		return default if default is not None else {}
	if isinstance(value, str):
		try:
			return frappe.parse_json(value)
		except Exception:
			return default if default is not None else {}
	return value


def _uid(prefix, index):
	return f"{prefix}_{index + 1}"


def _as_id_list(value):
	if value is None or value == "":
		return []
	if isinstance(value, (list, tuple, set)):
		return list(value)
	return [part.strip() for part in str(value).split(",") if part.strip()]


def _month_key_map(distribution):
	data = _json_arg(distribution, {}) or {}
	columns = data.get("columns") or []
	keys = [str(c.get("key") or "") for c in columns if c.get("key")]
	working_days = {
		str(c.get("key")): flt(c.get("working_days")) for c in columns if c.get("key")
	}
	rows = data.get("rows") or []
	by_task = {}
	for row in rows:
		tid = row.get("task_id")
		if tid:
			by_task[str(tid)] = row
	return data, columns, keys, working_days, by_task


def _dist_qty(dist_row, month_key):
	if not dist_row:
		return 0.0
	cell = (dist_row.get("cells") or {}).get(month_key) or {}
	return flt(cell.get("qty"))


def _default_equipment_rows():
	return [
		{"id": "eq_dozer", "name": "Dozer", "unit": "No", "source_type": "tab_total", "source_tab": "doz", "multiplier": 1},
		{"id": "eq_excavator", "name": "Chain Excavator", "unit": "No", "source_type": "tab_total", "source_tab": "exc", "multiplier": 1},
		{"id": "eq_grader", "name": "Grader", "unit": "No", "source_type": "tab_total", "source_tab": "grader", "multiplier": 1},
		{"id": "eq_roller", "name": "Single Drum Roller", "unit": "No", "source_type": "equipment", "source_id": "eq_grader", "multiplier": 1},
		{"id": "eq_loader", "name": "Loader", "unit": "No", "source_type": "tab_total", "source_tab": "loader", "multiplier": 1},
		{"id": "eq_backhoe", "name": "Backhoe Loader", "unit": "No", "source_type": "manual", "multiplier": 1, "manual_cells": {}},
		{"id": "eq_dump_truck", "name": "Dump Truck", "unit": "No", "source_type": "tab_total", "source_tab": "dt", "multiplier": 1},
		{"id": "eq_water_truck", "name": "Water Truck", "unit": "No", "source_type": "equipment", "source_id": "eq_grader", "multiplier": 2},
	]


def _default_fuel_rows(equipment_rows):
	rows = []
	seen = set()
	for eq in equipment_rows:
		name = str(eq.get("name") or "").lower()
		rate = 0.0
		for needle, value in FUEL_RATES:
			if needle in name:
				rate = value
				break
		rows.append({
			"id": f"fuel_{eq.get('id')}",
			"item": eq.get("name") or "Equipment",
			"equipment_id": eq.get("id"),
			"l_per_hour": rate,
			"hours_day": 8,
		})
		seen.add(eq.get("id"))
	if "eq_manual_equipment" not in seen:
		rows.append({
			"id": "fuel_manual", "item": "Manual Equipment",
			"equipment_id": "", "l_per_hour": 0, "hours_day": 8,
		})
	return rows


def _default_manpower_rows(equipment_rows):
	return [
		{"id": "mp_dozer", "role": "Dozer Operators", "source_type": "equipment", "source_id": "eq_dozer", "factor": 1, "manual_cells": {}},
		{"id": "mp_excavator", "role": "Excavator Operators", "source_type": "equipment", "source_id": "eq_excavator", "factor": 1, "manual_cells": {}},
		{"id": "mp_grader", "role": "Grader Operators", "source_type": "equipment", "source_id": "eq_grader", "factor": 1, "manual_cells": {}},
		{"id": "mp_loader", "role": "Loader Operators", "source_type": "equipment", "source_id": "eq_loader", "factor": 1, "manual_cells": {}},
		{"id": "mp_roller", "role": "Roller Operators", "source_type": "equipment", "source_id": "eq_roller", "factor": 1, "manual_cells": {}},
		{"id": "mp_driver", "role": "Dump Truck Drivers", "source_type": "equipment", "source_id": "eq_dump_truck", "factor": 1, "manual_cells": {}},
		{"id": "mp_assistant", "role": "Assistance Operators", "source_type": "equipment_sum", "source_ids": ["eq_dozer", "eq_excavator", "eq_grader", "eq_loader"], "factor": 1, "manual_cells": {}},
		{"id": "mp_manual", "role": "Manual Staff", "source_type": "manual", "factor": 1, "manual_cells": {}},
	]


def _default_crew_rows():
	return [
		{"id": "crew_dozer", "activity": "Dozer Production", "source_type": "machine_tab", "source_tab": "doz", "hourly_output": 0, "hours_day": 8, "crew_size": 1},
		{"id": "crew_grader", "activity": "Grader Production", "source_type": "machine_tab", "source_tab": "grader", "hourly_output": 0, "hours_day": 8, "crew_size": 1},
		{"id": "crew_manual", "activity": "Manual Crew", "source_type": "manual", "hourly_output": 0, "hours_day": 8, "crew_size": 1},
	]


@frappe.whitelist()
def get_resource_plan_seed(tasks=None, distribution=None, material_resources=None):
	tasks = _json_arg(tasks, []) or []
	distribution = _json_arg(distribution, {}) or {}
	material_resources = _json_arg(material_resources, []) or []
	_dist, _cols, _keys, _wd, by_task = _month_key_map(distribution)

	state = {}
	for tab in RESOURCE_TABS:
		state[tab] = {"rows": []}
	state["meta"] = {"seeded": 1}

	seen = set()
	seen_materials = {
		(str(r.get("task_id") or ""), str(r.get("item1") or r.get("id_mat") or ""))
		for r in material_resources
	}
	for task in tasks:
		tid = str(task.get("task_id") or "")
		if not tid:
			continue
		info = frappe.db.get_value("Task", tid, ["subject", "cost_break_down"], as_dict=True)
		if not info or not info.cost_break_down:
			continue
		try:
			cbd = frappe.get_doc("Cost Break Down", info.cost_break_down)
		except Exception:
			continue
		task_dist = by_task.get(tid) or {}
		task_qty = flt(task_dist.get("contract_qty") or task.get("contract_qty"))
		uom = task_dist.get("uom") or task.get("uom") or ""
		task_name = task.get("task_name") or info.subject or tid
		cbd_output = flt(cbd.hourly_output_eq)

		for material in cbd.materials or []:
			item = material.get("item") or material.get("item1")
			if not item:
				continue
			marker = (tid, str(item))
			if marker in seen_materials:
				continue
			seen_materials.add(marker)
			material_resources.append({
				"task_id": tid,
				"item1": item,
				"uom": material.get("unit") or "",
				"qty": flt(material.get("qty")),
			})

		for machine in cbd.machineries or []:
			label = str(machine.get("type") or "").lower()
			for key, keywords in MACHINE_KEYWORDS.items():
				if not any(word in label for word in keywords):
					continue
				marker = (key, tid)
				if marker in seen:
					break
				seen.add(marker)
				defaults = MACHINE_DEFAULTS[key]
				hourly_output = flt(machine.get("hourly_output")) or cbd_output or defaults["hourly_output"]
				row = {
					"id": _uid(key, len(state[key]["rows"])),
					"task_id": tid,
					"task_name": task_name,
					"uom": uom,
					"total_qty": task_qty,
					"eng_pct": 100,
					"hours_day": 8,
					"hourly_output": hourly_output,
					"source": "cbd",
				}
				if key == "dt":
					row.update({
						"distance": 13,
						"speed": 20,
						"load_unload_min": 9,
						"capacity": 16,
						"efficiency": 0.9,
						"availability": 0.85,
						"loose_factor": 1.25,
					})
				state[key]["rows"].append(row)
				break

	equipment_rows = _default_equipment_rows()
	state["equipment"]["rows"] = equipment_rows
	state["fuel"]["rows"] = _default_fuel_rows(equipment_rows)
	state["manpower"]["rows"] = _default_manpower_rows(equipment_rows)
	state["crew"]["rows"] = _default_crew_rows()

	fuel_row = {
		"id": "mat_fuel", "item": "Fuel", "unit": "Lt",
		"source_type": "fuel_total", "factor": 1, "divisor": 1,
		"manual_cells": {},
	}
	state["material"]["rows"].append(fuel_row)

	material_index = 1
	for resource in material_resources:
		tid = str(resource.get("task_id") or "")
		if not tid:
			continue
		task_dist = by_task.get(tid) or {}
		contract_qty = flt(task_dist.get("contract_qty"))
		if contract_qty <= 0:
			continue
		factor = flt(resource.get("qty")) / contract_qty
		state["material"]["rows"].append({
			"id": f"mat_{material_index}",
			"item": resource.get("item1") or resource.get("id_mat") or "Material",
			"unit": resource.get("uom") or "",
			"source_type": "workload",
			"task_id": tid,
			"factor": round(factor, 6),
			"divisor": 1,
			"manual_cells": {},
		})
		material_index += 1

	return state


def _machine_hourly_output(rows, tab):
	values = [flt(r.get("hourly_output")) for r in rows if flt(r.get("hourly_output")) > 0]
	if values:
		return sum(values) / len(values)
	return MACHINE_DEFAULTS.get(tab, {}).get("hourly_output", 0.0)


@frappe.whitelist()
def save_resource_plan_state(name=None, state=None):
	if not name:
		return {"ok": False}
	doc = frappe.get_doc("Master Plan", name)
	doc.check_permission("write")
	state = _json_arg(state, None)
	if state is None:
		return {"ok": False}
	frappe.db.set_value("Master Plan", name, "resource_plan_data", frappe.as_json(state), update_modified=False)
	return {"ok": True}


@frappe.whitelist()
def compute_resource_plan(distribution=None, state=None):
	distribution, columns, month_keys, working_days, by_task = _month_key_map(distribution)
	state = _json_arg(state, {}) or {}

	result = {
		"columns": columns,
		"months": month_keys,
		"working_days": working_days,
		"tabs": {},
	}

	machine_results = {}
	for tab in MACHINE_TABS:
		rows = (state.get(tab) or {}).get("rows") or []
		computed_rows = []
		totals = {key: 0.0 for key in month_keys}
		workload_totals = {key: 0.0 for key in month_keys}

		for row in rows:
			cells = {}
			engagement = flt(row.get("eng_pct") if row.get("eng_pct") is not None else 100)
			if engagement > 1.5:
				engagement = engagement / 100.0
			for key in month_keys:
				workload = _dist_qty(by_task.get(str(row.get("task_id") or "")), key) * engagement
				hours_day = flt(row.get("hours_day")) or 8
				wd = flt(working_days.get(key))
				if tab == "dt":
					distance = flt(row.get("distance")) or 13
					speed = flt(row.get("speed")) or 20
					load_minutes = flt(row.get("load_unload_min")) or 9
					capacity = flt(row.get("capacity")) or 16
					efficiency = flt(row.get("efficiency")) or 0.9
					availability = flt(row.get("availability")) or 0.85
					cycle_hours = (distance / speed) + (load_minutes / 60.0)
					effective_output = (capacity / cycle_hours) * efficiency * availability if cycle_hours else 0.0
					loose_factor = flt(row.get("loose_factor")) or 1.25
					denominator = efficiency * availability * effective_output * hours_day * wd
					machines = (workload * loose_factor / denominator) if denominator else 0.0
					daily_output = effective_output * hours_day
				else:
					hourly_output = flt(row.get("hourly_output"))
					daily_output = hourly_output * hours_day
					denominator = daily_output * wd
					machines = (workload / denominator) if denominator else 0.0

				cells[key] = {
					"workload": workload,
					"working_days": wd,
					"daily_output": daily_output,
					"machines": machines,
				}
				totals[key] += machines
				workload_totals[key] += workload

			computed_rows.append(dict(
				row,
				cells=cells,
				total=sum(flt(c.get("machines")) for c in cells.values()),
				total_workload=sum(flt(c.get("workload")) for c in cells.values()),
			))

		machine_results[tab] = {
			"rows": computed_rows,
			"totals": {
				key: {
					"raw": totals[key],
					"rounded": ceil(totals[key] - 1e-9) if totals[key] > 0 else 0,
				}
				for key in month_keys
			},
			"total_workload": workload_totals,
		}
		result["tabs"][tab] = machine_results[tab]

	equipment_rows = (state.get("equipment") or {}).get("rows") or _default_equipment_rows()
	equipment_results = {}
	equipment_by_id = {}
	for row in equipment_rows:
		equipment_results[str(row.get("id") or "")] = dict(row, cells={}, peak=0.0, total=0.0)
		equipment_by_id[str(row.get("id") or "")] = equipment_results[str(row.get("id") or "")]

	for _pass in range(4):
		for row in equipment_rows:
			target = equipment_results[str(row.get("id") or "")]
			for key in month_keys:
				value = 0.0
				source_type = row.get("source_type")
				if source_type == "tab_total":
					value = flt((machine_results.get(row.get("source_tab")) or {}).get("totals", {}).get(key, {}).get("rounded"))
				elif source_type == "tab_row":
					source_rows = (machine_results.get(row.get("source_tab")) or {}).get("rows") or []
					source = next((r for r in source_rows if str(r.get("id")) == str(row.get("source_row_id"))), None)
					if source:
						value = flt((source.get("cells") or {}).get(key, {}).get("machines"))
				elif source_type == "equipment":
					source = equipment_by_id.get(str(row.get("source_id") or ""))
					if source:
						value = flt((source.get("cells") or {}).get(key, {}).get("value"))
				elif source_type == "equipment_sum":
					for source_id in _as_id_list(row.get("source_ids")):
						source = equipment_by_id.get(str(source_id))
						if source:
							value += flt((source.get("cells") or {}).get(key, {}).get("value"))
				else:
					value = flt((row.get("manual_cells") or {}).get(key))
				multiplier = row.get("multiplier")
				multiplier = 1.0 if multiplier is None or multiplier == "" else flt(multiplier)
				value *= multiplier
				target["cells"][key] = {"value": value}
			target["peak"] = max([flt(c["value"]) for c in target["cells"].values()] or [0])
			target["total"] = sum(flt(c["value"]) for c in target["cells"].values())

	for target in equipment_results.values():
		target["peak"] = max([flt(c["value"]) for c in target["cells"].values()] or [0])
		target["total"] = sum(flt(c["value"]) for c in target["cells"].values())

	result["tabs"]["equipment"] = {
		"rows": list(equipment_results.values()),
		"totals": {
			key: sum(flt(r["cells"].get(key, {}).get("value")) for r in equipment_results.values())
			for key in month_keys
		},
		"peaks": {
			key: max([flt(r["cells"].get(key, {}).get("value")) for r in equipment_results.values()] or [0])
			for key in month_keys
		},
	}

	crew_rows = (state.get("crew") or {}).get("rows") or _default_crew_rows()
	crew_computed = []
	for row in crew_rows:
		if row.get("source_type") == "machine_tab":
			hourly_output = _machine_hourly_output(
				(machine_results.get(row.get("source_tab")) or {}).get("rows") or [],
				row.get("source_tab"),
			)
		else:
			hourly_output = flt(row.get("hourly_output"))
		hours_day = flt(row.get("hours_day")) or 8
		crew_size = flt(row.get("crew_size")) or 1
		daily_output = hourly_output * hours_day
		cells = {
			key: {"output": daily_output * crew_size * flt(working_days.get(key))}
			for key in month_keys
		}
		crew_computed.append(dict(
			row,
			hourly_output=hourly_output,
			daily_output=daily_output,
			cells=cells,
		))
	result["tabs"]["crew"] = {"rows": crew_computed}

	fuel_rows = (state.get("fuel") or {}).get("rows") or _default_fuel_rows(equipment_rows)
	fuel_computed = []
	fuel_totals = {key: 0.0 for key in month_keys}
	for row in fuel_rows:
		source = equipment_by_id.get(str(row.get("equipment_id") or ""))
		cells = {}
		for key in month_keys:
			count = flt((source.get("cells") or {}).get(key, {}).get("value")) if source else 0.0
			litres = count * flt(row.get("l_per_hour")) * (flt(row.get("hours_day")) or 8) * flt(working_days.get(key))
			cells[key] = {"equipment": count, "litres": litres}
			fuel_totals[key] += litres
		fuel_computed.append(dict(row, cells=cells, total=sum(flt(c["litres"]) for c in cells.values())))

	total_litres = sum(fuel_totals.values())
	scenario_pct = flt((state.get("fuel") or {}).get("scenario_pct")) or 85
	result["tabs"]["fuel"] = {
		"rows": fuel_computed,
		"totals": fuel_totals,
		"summary": {
			"total_litres": total_litres,
			"tanker_loads": total_litres / 13000.0 if total_litres else 0.0,
			"scenario_pct": scenario_pct,
			"scenario_litres": total_litres * scenario_pct / 100.0,
		},
	}

	manpower_rows = (state.get("manpower") or {}).get("rows") or _default_manpower_rows(equipment_rows)
	manpower_computed = []
	manpower_totals = {key: 0.0 for key in month_keys}
	for row in manpower_rows:
		cells = {}
		for key in month_keys:
			value = 0.0
			source_type = row.get("source_type")
			ids = _as_id_list(row.get("source_ids")) or ([row.get("source_id")] if row.get("source_id") else [])
			if source_type in ("equipment", "equipment_sum"):
				for source_id in ids:
					source = equipment_by_id.get(str(source_id))
					if source:
						value += flt((source.get("cells") or {}).get(key, {}).get("value"))
				factor = row.get("factor")
				factor = 1.0 if factor is None or factor == "" else flt(factor)
				value *= factor
			else:
				value = flt((row.get("manual_cells") or {}).get(key))
			cells[key] = {"headcount": value}
			manpower_totals[key] += value
		manpower_computed.append(dict(
			row,
			cells=cells,
			peak=max([flt(c["headcount"]) for c in cells.values()] or [0]),
			total=sum(flt(c["headcount"]) for c in cells.values()),
		))
	result["tabs"]["manpower"] = {"rows": manpower_computed, "totals": manpower_totals}

	material_rows = (state.get("material") or {}).get("rows") or []
	material_computed = []
	material_totals = {key: 0.0 for key in month_keys}
	for row in material_rows:
		cells = {}
		for key in month_keys:
			source_type = row.get("source_type")
			if source_type == "fuel_total":
				value = flt(fuel_totals.get(key))
			elif source_type == "workload":
				value = _dist_qty(by_task.get(str(row.get("task_id") or "")), key)
				divisor = flt(row.get("divisor")) or 1
				value = value * flt(row.get("factor")) / divisor
			else:
				value = flt((row.get("manual_cells") or {}).get(key))
			cells[key] = {"value": value}
			material_totals[key] += value
		material_computed.append(dict(
			row,
			cells=cells,
			total=sum(flt(c["value"]) for c in cells.values()),
		))
	result["tabs"]["material"] = {"rows": material_computed, "totals": material_totals}

	return result

