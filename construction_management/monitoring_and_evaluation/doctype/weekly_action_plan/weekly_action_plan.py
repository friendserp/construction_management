# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class WeeklyActionPlan(Document):
	def validate(self):
		if not self.is_new():
			self.refresh_timesheet_entries()
			self.refresh_daily_summaries()

	def refresh_timesheet_entries(self):
		self.timesheet_entries = []
		if self.is_new() or not self.name:
			return

		# Filter by direct link if possible, otherwise fallback to project/date
		where_clause = "tsd.project = %s AND DATE(tsd.from_time) BETWEEN %s AND %s"
		params = [self.project, self.from_date, self.to_date]

		if frappe.db.has_column("Timesheet", "custom_weekly_action_plan"):
			where_clause = "ts.custom_weekly_action_plan = %s"
			params = [self.name]

		rows = frappe.db.sql(
			f"""
			SELECT
				ts.name as timesheet,
				DATE(tsd.from_time) as report_date,
				tsd.task,
				t.subject as activity,
				tsd.hours,
				tsd.billing_rate,
				COALESCE(tsd.billing_amount, 0.0) as billing_amount
			FROM `tabTimesheet` ts
			INNER JOIN `tabTimesheet Detail` tsd ON tsd.parent = ts.name
			LEFT JOIN `tabTask` t ON t.name = tsd.task
			WHERE ts.docstatus = 1
				AND {where_clause}
			ORDER BY DATE(tsd.from_time), ts.name
			""",
			tuple(params),
			as_dict=True,
		)

		for row in rows:
			self.append(
				"timesheet_entries",
				{
					"timesheet": row.timesheet,
					"report_date": row.report_date,
					"task": row.task,
					"activity": row.activity,
					"hours": row.hours,
					"billing_rate": row.billing_rate,
					"billing_amount": row.billing_amount,
				},
			)

	def refresh_daily_summaries(self):
		self.daily_summaries = []
		if self.is_new():
			return

		daily_reports = frappe.get_all(
			"Daily Resource Report",
			filters={"weekly_action_plan": self.name},
			fields=[
				"name",
				"date",
				"direct_salary",
				"direct_overtime",
				"direct_incentive",
				"indirect_salary",
				"indirect_overtime",
				"indirect_incentive",
				"material_fuel_cost",
				"material_lubricant_cost",
				"material_spare_parts_cost",
				"material_construction_cost",
				"equipment_own_direct",
				"equipment_own_indirect",
				"equipment_rental_direct",
				"equipment_rental_indirect",
				"total_cost",
				"revenue",
				"profit_loss",
			],
			order_by="date asc",
		)

		actual_revenue = 0.0
		actual_cost = 0.0

		for drr in daily_reports:
			labor = (
				flt(drr.direct_salary)
				+ flt(drr.direct_overtime)
				+ flt(drr.direct_incentive)
				+ flt(drr.indirect_salary)
				+ flt(drr.indirect_overtime)
				+ flt(drr.indirect_incentive)
			)
			material = (
				flt(drr.material_fuel_cost)
				+ flt(drr.material_lubricant_cost)
				+ flt(drr.material_spare_parts_cost)
				+ flt(drr.material_construction_cost)
			)
			equipment = (
				flt(drr.equipment_own_direct)
				+ flt(drr.equipment_own_indirect)
				+ flt(drr.equipment_rental_direct)
				+ flt(drr.equipment_rental_indirect)
			)

			actual_revenue += flt(drr.revenue)
			actual_cost += flt(drr.total_cost)

			self.append(
				"daily_summaries",
				{
					"daily_resource_report": drr.name,
					"report_date": drr.date,
					"labor_cost": labor,
					"material_cost": material,
					"equipment_cost": equipment,
					"total_cost": drr.total_cost,
					"revenue": drr.revenue,
					"profit_loss": drr.profit_loss,
				},
			)

		self.actual_revenue = actual_revenue
		self.actual_cost = actual_cost
		self.actual_profit = actual_revenue - actual_cost
		self.variance_revenue = actual_revenue - flt(self.total_revenue)
		self.variance_cost = actual_cost - flt(self.total_cost)
		self.variance_profit = self.actual_profit - flt(self.projected_profit)


@frappe.whitelist()
def get_wap_activities_query(doctype, txt, searchfield, start, page_len, filters):
	wap = filters.get("wap")
	if not wap:
		return []

	return frappe.db.sql(
		"""
		SELECT DISTINCT 
			t.name, t.subject
		FROM `tabTask` t
		INNER JOIN `tabWeekly Action Plan Item` wapi ON wapi.activity = t.name
		WHERE wapi.parent = %s
			AND (t.name LIKE %s OR t.subject LIKE %s)
		LIMIT %s, %s
		""",
		(wap, f"%{txt}%", f"%{txt}%", start, page_len),
	)


@frappe.whitelist()
def get_cbd_details(task):
	"""Fetch Cost Break Down details for a given Task."""
	cbd_name = frappe.db.get_value("Task", task, "cost_break_down")

	if not cbd_name:
		task_subject = frappe.db.get_value("Task", task, "subject")
		cbd_name = frappe.db.get_value("Cost Break Down", {"work_item": task_subject}, "name")

	if not cbd_name:
		return None

	cbd_doc = frappe.get_doc("Cost Break Down", cbd_name)

	resources = {
		"total_unit_cost": cbd_doc.total_unit_cost,
		"productivity": cbd_doc.productivity,
		"materials": [],
		"manpower": [],
		"machinery": [],
	}

	for m in cbd_doc.materials:
		resources["materials"].append({
			"item": m.item,
			"unit": m.unit,
			"consumption_rate": m.qty,
			"unit_price": m.rate,
		})

	for m in cbd_doc.manpowers:
		resources["manpower"].append({
			"designation": m.labour,
			"no": m.no,
			"uf": m.uf,
			"cost_rate": m.indexed_hourly_cost,
		})

	for m in cbd_doc.machineries:
		resources["machinery"].append({
			"equipment_type": m.type,
			"fuel_rate": m.fuel_rate if hasattr(m, "fuel_rate") else 0,
			"rental_rate": m.hourly_rental,
		})

	return resources


def update_weekly_plan_monitoring(wap_name):
	"""Update monitoring fields on a submitted Weekly Action Plan."""
	doc = frappe.get_doc("Weekly Action Plan", wap_name)
	doc.refresh_daily_summaries()
	doc.db_update()
	update = {
		"actual_revenue": doc.actual_revenue,
		"actual_cost": doc.actual_cost,
		"actual_profit": doc.actual_profit,
		"variance_revenue": doc.variance_revenue,
		"variance_cost": doc.variance_cost,
		"variance_profit": doc.variance_profit,
	}
	frappe.db.set_value("Weekly Action Plan", wap_name, update, update_modified=True)
	_save_child_table(doc, "daily_summaries")
	return doc.daily_summaries


def _save_child_table(doc, fieldname):
	"""Persist child table rows on submitted parent."""
	parent = doc.name
	parenttype = doc.doctype
	parentfield = fieldname

	frappe.db.delete(doc.meta.get_field(fieldname).options, {
		"parent": parent,
		"parenttype": parenttype,
		"parentfield": parentfield,
	})

	for row in doc.get(fieldname) or []:
		row.parent = parent
		row.parenttype = parenttype
		row.parentfield = parentfield
		row.db_insert()


@frappe.whitelist()
def refresh_daily_summaries(wap_name):
	return update_weekly_plan_monitoring(wap_name)


@frappe.whitelist()
def create_timesheets_from_wap(wap_name):
	from construction_management.monitoring_and_evaluation.timesheet_utils import (
		create_timesheets_from_weekly_plan,
	)

	return create_timesheets_from_weekly_plan(wap_name)
