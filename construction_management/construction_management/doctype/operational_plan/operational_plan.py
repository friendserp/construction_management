# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, flt, getdate

from construction_management.construction_management.doctype.master_plan.master_plan import (
	get_monthly_distribution,
	recompute_working_days,
)

FINISH_TO_START = "Finish to Start"


class OperationalPlan(Document):
	pass


@frappe.whitelist()
def get_operational_plan_data(master_plan, start_date=None, end_date=None):
	"""Snapshot the linked Master Plan into this Operational Plan for [start_date, end_date].

	Everything is derived from the Master Plan engine (same working day weights, same
	manual overrides), so the task list, the monthly workload/cashflow and the critical
	path all stay consistent with the Master Plan at the moment of loading.
	"""
	if not master_plan:
		frappe.throw(_("Please select a Master Plan first."))
	if not start_date or not end_date:
		frappe.throw(_("Please set the Start Date and End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if start_date > end_date:
		frappe.throw(_("Start Date cannot be after End Date."))

	mp = frappe.get_doc("Master Plan", master_plan)
	country = mp.holiday_country or "ET"
	season_length = mp.season_length_months or 4

	tasks = _task_payload(mp, start_date, end_date)
	holidays = [
		{
			"day_type": h.day_type or "Holiday",
			"from_date": str(h.from_date),
			"to_date": str(h.to_date or h.from_date),
		}
		for h in mp.holiday
		if h.from_date
	]
	overrides = [
		{"task_id": d.task_id, "month": d.month, "qty": d.qty}
		for d in mp.distribution
		if d.task_id and d.month
	]

	# Distribute the WHOLE project from the Master Plan, then keep only the months
	# inside this operational year. This way each task's planned qty here is that
	# year's share of the distribution, not the full project quantity.
	full_tasks = _task_payload(mp, getdate(mp.start_date), getdate(mp.end_date))
	full_distribution = get_monthly_distribution(
		holiday_list=mp.holiday_list,
		country=country,
		holidays=holidays,
		start_date=mp.start_date,
		end_date=mp.end_date,
		tasks=full_tasks,
		overrides=overrides,
		season_length_months=season_length,
		weekly_off=mp.weekly_off,
	)
	distribution = _clip_distribution(full_distribution, start_date, end_date)

	calendar = recompute_working_days(
		holidays=holidays,
		country=country,
		weekly_off=mp.weekly_off,
		start_date=start_date,
		end_date=end_date,
		season_length_months=season_length,
	)
	calendar["holiday_rows"] = [
		{
			"day_type": h.day_type or "Holiday",
			"holiday_name": h.holiday_name,
			"from_date": str(h.from_date),
			"to_date": str(h.to_date or h.from_date),
			"total": h.total,
			"month": h.month,
		}
		for h in mp.holiday
		if h.from_date and start_date <= getdate(h.from_date) <= end_date
	]

	sequencing, critical, crit_names, crit_days = _sequencing_and_critical_path(
		distribution, tasks, start_date
	)

	return {
		"distribution": distribution,
		"calendar": calendar,
		"tasks": tasks,
		"sequencing": sequencing,
		"critical_path": critical,
		"tasks_on_critical_path": crit_names,
		"critical_path_duration": crit_days,
	}


def _clip_distribution(distribution, window_start, window_end):
	"""Keep only the month columns inside [window_start, window_end].

	The planned qty of each row becomes the sum of those months, so a one year
	plan carries the year share of the workload instead of the whole project.
	"""
	window_start = getdate(window_start)
	window_end = getdate(window_end)

	columns = [c for c in distribution.get("columns", []) if _month_in_window(c["key"], window_start, window_end)]
	keys = {c["key"] for c in columns}

	rows = []
	for r in distribution.get("rows", []):
		cells = {k: v for k, v in r.get("cells", {}).items() if k in keys}
		if not cells:
			continue
		distributed = round(sum(flt(v.get("qty")) for v in cells.values()), 4)
		total_wd = sum(cint(v.get("working_days")) for v in cells.values())
		rate = flt(r.get("unit_rate"))
		qty = flt(r.get("contract_qty"))
		rows.append(
			{
				"task_id": r.get("task_id"),
				"task_name": r.get("task_name"),
				"series": r.get("series"),
				"uom": r.get("uom"),
				"contract_qty": qty,
				"unit_rate": rate,
				"total_planned_qty": qty,
				"distributed_qty": distributed,
				"has_manual": any(v.get("manual") for v in cells.values()),
				"total_planned_amount": round(qty * rate, 2),
				"total_working_days": total_wd,
				"cells": cells,
			}
		)

	return {
		"columns": columns,
		"rows": rows,
		"season_length_months": distribution.get("season_length_months"),
	}


def _month_in_window(key, window_start, window_end):
	year, month = (int(part) for part in key.split("-"))
	month_start = getdate(f"{year:04d}-{month:02d}-01")
	month_end = _month_end(year, month)
	return month_start <= window_end and month_end >= window_start


def _month_end(year, month):
	first = getdate(f"{year:04d}-{month:02d}-01")
	if month == 12:
		nxt = getdate(f"{year + 1:04d}-01-01")
	else:
		nxt = getdate(f"{year:04d}-{month + 1:02d}-01")
	return add_days(nxt, -1)


def _task_payload(mp, window_start, window_end):
	payload = []
	for w in mp.wbs:
		if not w.task_id:
			continue
		start = getdate(w.start_date or mp.start_date)
		end = getdate(w.finish_date or mp.end_date)
		payload.append(
			{
				"task_id": w.task_id,
				"task_name": w.task_name,
				"series": w.series,
				"uom": w.uom,
				"contract_qty": w.contract_qty,
				"task_unit_rate": w.task_unit_rate,
				"start_date": str(max(start, window_start)),
				"finish_date": str(min(end, window_end)),
				"executed_qty": w.executed_qty,
				"remaining_qty": w.remaining_qty,
				"duration": w.duration,
				"productivity": w.productivity,
				"activity_physical_weight": w.activity_physical_weight,
				"predecessor": w.predecessor,
			}
		)
	return payload


def _relationships(meta, task_id):
	raw = meta.get(task_id, {}).get("predecessor") or ""
	return [p for p in raw.replace(",", " ").split() if p]


def _sequencing_and_critical_path(distribution, tasks, start_date):
	"""Build a Finish-to-Start sequence and an ES/EF/LS/LF critical path.

	Dependencies come from the WBS ``predecessor`` field when present. Tasks without a
	predecessor are treated as independent, so their earliest start is their own planned
	start date and the critical path follows the longest chain to the project finish.
	"""
	meta = {t["task_id"]: t for t in tasks}
	rows = distribution.get("rows") or []
	if not rows:
		return [], [], "", 0

	nodes = {}
	for r in rows:
		t = meta.get(r["task_id"], {})
		tid = r["task_id"]
		planned_start = getdate(t.get("start_date") or start_date)
		planned_finish = getdate(t.get("finish_date") or planned_start)
		span = max(date_diff(planned_finish, planned_start) + 1, 1)
		nodes[tid] = {
			"id": tid,
			"name": r.get("task_name"),
			"working_days": max(int(r.get("total_working_days") or 0), 0),
			"span": span,
			"planned_start": planned_start,
		}

	preds = {}
	for tid in nodes:
		preds[tid] = [p for p in _relationships(meta, tid) if p in nodes]

	# Forward pass: earliest start / finish. Each task keeps its planned span, but is
	# pushed later if a predecessor finishes after its planned start.
	es = {tid: nodes[tid]["planned_start"] for tid in nodes}
	for _ in range(len(nodes) + 1):
		changed = False
		for tid, node in nodes.items():
			base = node["planned_start"]
			for p in preds[tid]:
				cand = add_days(es[p], nodes[p]["span"])
				if cand > base:
					base = cand
			if base != es[tid]:
				es[tid] = base
				changed = True
		if not changed:
			break

	ef = {tid: add_days(es[tid], nodes[tid]["span"] - 1) for tid in nodes}
	project_finish = max(ef.values())

	succs = {tid: [] for tid in nodes}
	for tid, plist in preds.items():
		for p in plist:
			succs[p].append(tid)

	# Backward pass: latest finish / start.
	lf = {tid: project_finish for tid in nodes}
	ls = {tid: add_days(project_finish, -(nodes[tid]["span"] - 1)) for tid in nodes}
	for _ in range(len(nodes) + 1):
		changed = False
		for tid, node in nodes.items():
			cand_finish = project_finish
			if succs[tid]:
				cand_finish = min(add_days(ls[s], -1) for s in succs[tid])
			if cand_finish < lf[tid]:
				lf[tid] = cand_finish
				changed = True
			cand_start = add_days(lf[tid], -(node["span"] - 1))
			if cand_start != ls[tid]:
				ls[tid] = cand_start
				changed = True
		if not changed:
			break

	sequencing = []
	critical = []
	critical_names = []
	for tid, node in nodes.items():
		pred = preds[tid][0] if preds[tid] else None
		successor = succs[tid][0] if succs[tid] else None
		sequencing.append(
			{
				"activity": tid,
				"act_name": tid,
				"duration": node["span"],
				"relationship_type": FINISH_TO_START,
				"to_activity": successor,
				"lag_days": 0,
				"lead_days": 0,
				"predecessor_activity": pred,
				"successor_activity": successor,
			}
		)

		free_float = date_diff(ls[tid], es[tid])
		critical.append(
			{
				"activity": tid,
				"task_id": tid,
				"es": es[tid],
				"ef": ef[tid],
				"ls": ls[tid],
				"lf": lf[tid],
				"free_float": free_float,
			}
		)
		if free_float <= 0:
			critical_names.append(tid)

	critical_days = date_diff(project_finish, min(es.values())) + 1
	return sequencing, critical, ", ".join(critical_names), critical_days
