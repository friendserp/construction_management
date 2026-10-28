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
from construction_management.construction_management.doctype.monthly_plan.monthly_plan import (
	spread_over_days,
)


class WeeklyPlan(Document):
	pass


@frappe.whitelist()
def get_weekly_plan_data(monthly_plan, start_date=None, end_date=None):
	"""Expand one week of the linked Monthly Plan into days.

	The Monthly Plan already sized each week (``week_1`` .. ``week_5``). The weekly plan
	picks the column that matches the selected window and splits that week's quantity
	across the week's working days, so every level reconciles: days sum to the week and
	the weeks sum to the month.
	"""
	if not monthly_plan:
		frappe.throw(_("Please select a Monthly Plan first."))
	if not start_date or not end_date:
		frappe.throw(_("Please set the Start Date and End Date first."))

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if start_date > end_date:
		frappe.throw(_("Start Date cannot be after End Date."))

	mp = frappe.get_doc("Monthly Plan", monthly_plan)
	master = frappe.get_doc("Master Plan", mp.master_plan) if mp.master_plan else None
	country = (master.holiday_country if master else None) or "ET"
	season_length = (master.season_length_months if master else None) or 4
	weekly_off = (master.weekly_off if master else None) or mp.weekly_off

	week_no = date_diff(start_date, getdate(mp.start_date)) // 7 + 1
	week_field = f"week_{week_no}"

	holidays = [
		{
			"day_type": h.day_type or "Holiday",
			"from_date": str(h.from_date),
			"to_date": str(h.to_date or h.from_date),
		}
		for h in mp.holiday
		if h.from_date
	]
	non_working = _non_working_date_set(holidays)

	days = [add_days(start_date, i) for i in range(date_diff(end_date, start_date) + 1)]
	day_index = {d: i + 1 for i, d in enumerate(days)}

	detail_by_activity = {d.activity: d for d in mp.monthly_plan_detail}
	cashflow_by_task = {c.task_id: c for c in mp.weekly_task_cashflow}

	detail = []
	workload = []
	cashflow = []
	for row in mp.weekly_task_workload:
		task_id = row.task_id
		if not task_id:
			continue
		week_qty = flt(row.get(week_field))

		win_start = max(getdate(row.start_date), start_date) if row.start_date else start_date
		win_end = min(getdate(row.end_date), end_date) if row.end_date else end_date
		if win_start > win_end:
			win_start, win_end = start_date, end_date
		working = [d for d in days if win_start <= d <= win_end and d not in non_working]

		cells = spread_over_days(week_qty, working)
		rate = flt(row.rate)

		base_detail = detail_by_activity.get(task_id)
		detail.append(
			{
				"activity": task_id,
				"activity_name": row.task_name or (base_detail.activity_name if base_detail else None),
				"uom": row.uom or (base_detail.uom if base_detail else None),
				"rate": rate,
				"amount": flt(row.amount),
				"planned_amount": round(week_qty * rate, 2),
				"quantity": flt(row.quantity),
				"up_to_end_of_previous_month_executed": flt(
					base_detail.up_to_end_of_previous_month_executed if base_detail else 0
				),
				"remaining_planned_qty": flt(base_detail.remaining_planned_qty if base_detail else 0),
				"planned": week_qty,
				"this_month_executed": 0,
				"duration": cint(base_detail.duration if base_detail else 0),
				"planned_day": len(working),
				"productivity": flt(base_detail.productivity if base_detail else 0),
				"start_date": str(win_start),
				"end_date": str(win_end),
				"to_date_executed": flt(base_detail.to_date_executed if base_detail else 0),
			}
		)

		wl = {
			"task_id": task_id,
			"task_name": row.task_name,
			"uom": row.uom,
			"planned": week_qty,
			"start_date": str(win_start),
			"end_date": str(win_end),
			"rate": rate,
		}
		for d in days:
			wl[f"day_{day_index[d]}"] = cells.get(d, 0)
		workload.append(wl)

		cf_row = cashflow_by_task.get(task_id)
		week_amount = flt(cf_row.get(week_field)) if cf_row else round(week_qty * rate, 2)
		amount_cells = spread_over_days(week_amount, working)
		cf = {
			"task_id": task_id,
			"task_name": row.task_name,
			"uom": row.uom,
			"planned_amount": week_amount,
			"start_date": str(win_start),
			"end_date": str(win_end),
		}
		for d in days:
			cf[f"day_{day_index[d]}"] = amount_cells.get(d, 0)
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
		for h in mp.holiday
		if h.from_date and start_date <= getdate(h.from_date) <= end_date
	]

	return {
		"detail": detail,
		"workload": workload,
		"cashflow": cashflow,
		"calendar": calendar,
		"week_no": week_no,
	}
