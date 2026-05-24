# Copyright (c) 2026, Friends ERP and contributors

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate


def create_timesheets_from_weekly_plan(wap_name):
	"""Create submitted Timesheets from Weekly Action Plan (one timesheet per day)."""
	wap = frappe.get_doc("Weekly Action Plan", wap_name)
	if not wap.project:
		frappe.throw(_("Project is required on Weekly Action Plan"))

	company = frappe.db.get_value("Project", wap.project, "company")
	employee = frappe.db.get_value("Employee", {"status": "Active"}, "name", order_by="creation desc")
	if not employee:
		frappe.throw(_("No active Employee found for Timesheet creation"))

	activity_type = frappe.db.get_value("Activity Type", {}, "name") or "Planning"
	working_days = _working_days(wap.from_date, wap.to_date)
	created = []

	report_date = getdate(wap.from_date)
	end_date = getdate(wap.to_date)

	while report_date <= end_date:
		ts = _get_timesheet_for_date(wap, employee, report_date)
		hour_offset = 0
		added_rows = 0

		for item in wap.action_plan_items:
			if not item.activity or not flt(item.qty):
				continue
			if ts and _has_time_log(ts, item.activity, report_date):
				continue

			unit_rate = flt(item.unit_price_share) or (
				flt(item.expected_amount) / flt(item.qty) if flt(item.qty) else 0
			)
			daily_qty = flt(item.qty) / working_days
			hours = max(daily_qty, 0.5)

			if not ts:
				ts = frappe.new_doc("Timesheet")
				ts.company = company
				ts.employee = employee
				ts.parent_project = wap.project
				if frappe.db.has_column("Timesheet", "custom_weekly_action_plan"):
					ts.custom_weekly_action_plan = wap.name

			start_dt = datetime.combine(report_date, datetime.min.time()) + timedelta(
				hours=8 + hour_offset
			)
			end_dt = start_dt + timedelta(hours=hours)
			hour_offset += hours + 0.5

			ts.append(
				"time_logs",
				{
					"activity_type": activity_type,
					"project": wap.project,
					"task": item.activity,
					"from_time": start_dt,
					"to_time": end_dt,
					"hours": hours,
					"billing_hours": hours,
					"billing_rate": unit_rate,
					"billing_amount": hours * unit_rate,
					"is_billable": 1,
				},
			)
			added_rows += 1

		if added_rows:
			if ts.is_new():
				ts.insert(ignore_permissions=True)
			else:
				ts.save(ignore_permissions=True)
			if ts.docstatus == 0:
				ts.submit()
			if ts.name not in created:
				created.append(ts.name)

		report_date = add_days(report_date, 1)

	wap.refresh_timesheet_entries()
	if wap.docstatus == 1:
		_save_wap_child_table(wap, "timesheet_entries")
	else:
		wap.save(ignore_permissions=True)

	return created


def _get_timesheet_for_date(wap, employee, report_date):
	"""Return draft/submitted timesheet for this WAP day if it exists."""
	if frappe.db.has_column("Timesheet", "custom_weekly_action_plan"):
		name = frappe.db.get_value(
			"Timesheet",
			{
				"custom_weekly_action_plan": wap.name,
				"employee": employee,
				"docstatus": ["<", 2],
			},
			"name",
		)
		if name:
			return frappe.get_doc("Timesheet", name)

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT ts.name
		FROM `tabTimesheet` ts
		INNER JOIN `tabTimesheet Detail` tsd ON tsd.parent = ts.name
		WHERE ts.docstatus = 0
			AND ts.employee = %s
			AND tsd.project = %s
			AND DATE(tsd.from_time) = %s
		LIMIT 1
		""",
		(employee, wap.project, report_date),
	)
	if rows:
		return frappe.get_doc("Timesheet", rows[0][0])
	return None


def _has_time_log(ts, task, report_date):
	for row in ts.time_logs:
		if row.task == task and getdate(row.from_time) == getdate(report_date):
			return True
	return False


def _working_days(from_date, to_date):
	if from_date and to_date:
		return max((getdate(to_date) - getdate(from_date)).days + 1, 1)
	return 7


def refresh_wap_timesheet_entries(wap_name):
	wap = frappe.get_doc("Weekly Action Plan", wap_name)
	wap.refresh_timesheet_entries()
	if wap.docstatus == 1:
		_save_wap_child_table(wap, "timesheet_entries")
	else:
		wap.save(ignore_permissions=True)
	return wap.timesheet_entries


def _save_wap_child_table(doc, fieldname):
	parentfield = fieldname
	child_doctype = doc.meta.get_field(fieldname).options

	frappe.db.delete(
		child_doctype,
		{"parent": doc.name, "parenttype": doc.doctype, "parentfield": parentfield},
	)
	for row in doc.get(fieldname) or []:
		row.parent = doc.name
		row.parenttype = doc.doctype
		row.parentfield = parentfield
		row.db_insert()
