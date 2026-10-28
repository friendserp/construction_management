# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, flt, getdate

from construction_management.construction_management.doctype.master_plan.master_plan import (
	_non_working_date_set,
	recompute_working_days,
)

MONTH_FIELDS = {
	1: "jan",
	2: "feb",
	3: "mar",
	4: "apr",
	5: "may",
	6: "jun",
	7: "jul",
	8: "aug",
	9: "sep",
	10: "oct",
	11: "nov",
	12: "dec",
}


class MonthlyPlan(Document):
	pass


@frappe.whitelist()
def get_monthly_plan_data(operational_plan, start_date=None, end_date=None):
	"""Break one month of the linked Operational Plan into days.

	The month's quantity of every task is read straight from the Operational Plan's
	monthly distribution (``tasks_workload_distribution``), so the monthly plan is a
	synchronized child of the year plan. That quantity is then spread evenly over the
	working days of the month (holidays and the weekly off are skipped).
	"""
	if not operational_plan:
		frappe.throw(_("Please select an Operational Plan first."))
	if not start_date or not end_date:
		frappe.throw(_("Please set the Start Date and End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if start_date > end_date:
		frappe.throw(_("Start Date cannot be after End Date."))

	op = frappe.get_doc("Operational Plan", operational_plan)
	mp = frappe.get_doc("Master Plan", op.master_plan_name) if op.master_plan_name else None
	country = (mp.holiday_country if mp else None) or "ET"
	season_length = (mp.season_length_months if mp else None) or 4
	weekly_off = (mp.weekly_off if mp else None) or op.weekly_off

	month_field = MONTH_FIELDS[start_date.month]

	holidays = [
		{
			"day_type": h.day_type or "Holiday",
			"from_date": str(h.from_date),
			"to_date": str(h.to_date or h.from_date),
		}
		for h in op.holiday
		if h.from_date
	]
	non_working = _non_working_date_set(holidays)

	days = [add_days(start_date, i) for i in range(date_diff(end_date, start_date) + 1)]
	blocks = week_blocks(start_date, end_date)

	detail = []
	workload = []
	cashflow = []
	for row in op.tasks_workload_distribution:
		task_id = row.activity or row.activity_name
		if not task_id:
			continue
		month_qty = flt(row.get(month_field))
		contract = flt(row.contract_qty)
		rate = flt(row.rate)
		if not month_qty and not contract:
			continue

		win_start = max(getdate(row.start_date), start_date) if row.start_date else start_date
		win_end = min(getdate(row.end_date), end_date) if row.end_date else end_date
		if win_start > win_end:
			win_start, win_end = start_date, end_date
		working = [d for d in days if win_start <= d <= win_end and d not in non_working]

		cells = spread_over_days(month_qty, working)
		week_cells = {k: round(sum(cells.get(d, 0) for d in blk), 4) for k, blk in enumerate(blocks, 1)}

		detail.append(
			{
				"activity": task_id,
				"activity_name": row.task_name,
				"uom": row.uom,
				"rate": rate,
				"amount": round(contract * rate, 2),
				"planned_amount": round(month_qty * rate, 2),
				"quantity": contract,
				"up_to_end_of_previous_month_executed": 0,
				"remaining_planned_qty": flt(row.get("total_remaining_qty")),
				"planned": month_qty,
				"this_month_executed": 0,
				"duration": cint(row.get("duration") or 0),
				"planned_day": len(working),
				"productivity": flt(row.get("productivity")),
				"start_date": str(win_start),
				"end_date": str(win_end),
				"to_date_executed": flt(row.get("to_date_excuted_qty")),
			}
		)

		base = {
			"task_id": task_id,
			"task_name": row.task_name,
			"uom": row.uom,
			"quantity": contract,
			"planned": month_qty,
			"start_date": str(win_start),
			"end_date": str(win_end),
			"rate": rate,
			"amount": round(contract * rate, 2),
			"planned_amount": round(month_qty * rate, 2),
		}
		wl = dict(base)
		cf = dict(base)
		for k in range(1, len(blocks) + 1):
			wl[f"week_{k}"] = week_cells.get(k, 0)
			cf[f"week_{k}"] = round(week_cells.get(k, 0) * rate, 2)
		workload.append(wl)
		cashflow.append(cf)

	calendar = recompute_working_days(
		holidays=holidays,
		country=country,
		weekly_off=weekly_off,
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
		for h in op.holiday
		if h.from_date and start_date <= getdate(h.from_date) <= end_date
	]

	return {
		"detail": detail,
		"workload": workload,
		"cashflow": cashflow,
		"calendar": calendar,
		"month_field": month_field,
	}


def spread_over_days(qty, working_dates):
	"""Split a quantity evenly over the given (sorted) working dates.

	The rounding drift is parked on the last working day so the cells sum back to
	``qty`` exactly.
	"""
	n = len(working_dates)
	if n == 0 or not qty:
		return {}
	cells = {}
	allocated = 0.0
	for i, d in enumerate(working_dates):
		if i == n - 1:
			val = round(qty - allocated, 4)
		else:
			val = round(qty / n, 4)
			allocated += val
		cells[d] = val
	return cells


def week_blocks(start_date, end_date):
	"""Seven day blocks (Mon..Sun style) covering the window.

	Week N is days ``[start + 7*(N-1), start + 7*N - 1]`` clipped to the window, so the
	blocks line up exactly with the Weekly Plan's week selector.
	"""
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	total = date_diff(end_date, start_date) + 1
	blocks = []
	for i in range(max(1, -(-total // 7))):
		blk_start = add_days(start_date, i * 7)
		blk_end = add_days(start_date, i * 7 + 6)
		if blk_end > end_date:
			blk_end = end_date
		blocks.append([add_days(blk_start, j) for j in range(date_diff(blk_end, blk_start) + 1)])
	return blocks
