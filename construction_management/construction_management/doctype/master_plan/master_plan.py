# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

from bisect import bisect_left

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
	tasks=None, season_length_months=6, overrides=None,
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


# ---------------------------------------------------------------------------
# Cost Break Down → resource rows (machinery / manpower / material)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_task_resources(project=None, tasks=None):
	tasks = frappe.parse_json(tasks) if isinstance(tasks, str) else (tasks or [])
	machinery, manpower, material = [], [], []
	meta = frappe.get_meta("Task")
	task_fields = ["name", "subject", "cost_break_down", "task_duration_in_hour",
	               "task_duration_in_days", "working_hour_per_day"]
	if meta.has_field("custom_task_duration_in_hour"):
		task_fields.append("custom_task_duration_in_hour")
	if meta.has_field("custom_contract_qty"):
		task_fields.append("custom_contract_qty")

	for task in tasks:
		tid = task.get("task_id")
		if not tid:
			continue
		info = frappe.db.get_value("Task", tid, task_fields, as_dict=True)
		if not info or not info.cost_break_down:
			continue

		start, end = task.get("start_date"), task.get("finish_date")
		year = (start or "")[:4]
		task_qty = flt(info.get("custom_contract_qty"))
		working_hour = flt(info.working_hour_per_day) or 8
		dur_hours = flt(info.get("custom_task_duration_in_hour"))
		if dur_hours <= 0:
			dur_hours = flt(info.task_duration_in_hour)
		if dur_hours <= 0:
			dur_hours = flt(info.task_duration_in_days) * working_hour
		if dur_hours <= 0 and start and end:
			dur_hours = max(date_diff(getdate(end), getdate(start)) + 1, 1) * working_hour

		cbd = frappe.get_doc("Cost Break Down", info.cost_break_down)
		hourly_output_eq = flt(cbd.hourly_output_eq)
		hourly_output_mp = flt(cbd.hourly_output_mp)

		for m in cbd.machineries:
			qty = flt(m.no)
			uf = flt(m.uf) or 1
			rental = flt(m.hourly_rental)
			hourly = flt(m.hourly_cost)
			hourly_output = flt(m.hourly_output)
			if qty <= 0 and hourly_output > 0 and task_qty > 0 and dur_hours > 0:
				qty = round(task_qty / (hourly_output * dur_hours), 4)
				if rental:
					hourly = qty * uf * rental
			elif qty <= 0 and rental and hourly:
				qty = round(hourly / (uf * rental), 4)
			if hourly <= 0 and qty and rental:
				hourly = qty * uf * rental
			machinery.append({
				"year": year, "task_id": tid, "task_name": info.subject, "type": m.type,
				"qty": qty, "task_duration_in_hour": dur_hours, "working_hour": working_hour,
				"uf": flt(m.uf), "rental_rate": rental, "total_hourly_cost": hourly,
				"total_cost": round(hourly * dur_hours, 2),
				"start_date": start, "end_date": end, "hourly_output_eq": hourly_output_eq,
			})

		for m in cbd.manpowers:
			qty = flt(m.no)
			uf = flt(m.uf) or 1
			hourly = flt(m.hourly_cost)
			if hourly <= 0 and qty:
				hourly = qty * uf * flt(m.indexed_hourly_cost)
			manpower.append({
				"year": year, "task_id": tid, "task_name": info.subject,
				"id_map": m.labour, "job_title": m.labour, "is_major_manpower": 0,
				"qty": qty, "uf": flt(m.uf), "task_duration_in_hour": dur_hours,
				"working_hour": working_hour, "rental_rate": flt(m.indexed_hourly_cost),
				"total_hourly_cost": hourly, "total_cost": round(hourly * dur_hours, 2),
				"start_date": start, "end_date": end, "hourly_output_mp": hourly_output_mp,
			})

		for m in cbd.materials:
			qty = flt(m.qty)
			rate = flt(m.rate)
			material.append({
				"year": year, "task_id": tid, "task_name": info.subject,
				"id_mat": m.item, "item1": m.item, "is_major_material": 0,
				"uom": m.unit, "qty": qty, "task_duration_in_hour": dur_hours,
				"working_hour": working_hour, "unit_price": rate,
				"total_cost": round(qty * rate, 2),
				"start_date": start, "end_date": end,
			})

	return {"machinery": machinery, "manpower": manpower, "material": material}
