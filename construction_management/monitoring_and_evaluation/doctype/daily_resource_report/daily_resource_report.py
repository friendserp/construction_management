# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, getdate


def get_material_cost_category(item_group, parent_item_group, sub_cat):
	item_group = item_group or ""
	parent_item_group = parent_item_group or ""
	sub_cat = sub_cat or ""

	if item_group in ["Gas oil", "Regular (Benzene)", "Kerosene (Nechi Gas)"]:
		return "Fuel"
	if sub_cat == "Oil and Lubricants":
		return "Lubricant"
	if item_group == "Spare Parts":
		return "Spare Parts"
	if parent_item_group == "Construction Material":
		return "Construction Material"
	return "Other"


class DailyResourceReport(Document):
	def validate(self):
		self.validate_weekly_plan()
		self.fetch_daily_costs_data()
		self.fetch_planned_targets()
		self.calculate_totals()

	def validate_weekly_plan(self):
		if not self.weekly_action_plan:
			return

		wap = frappe.db.get_value(
			"Weekly Action Plan",
			self.weekly_action_plan,
			["project", "from_date", "to_date"],
			as_dict=True,
		)
		if not wap:
			return

		if wap.project != self.project:
			frappe.throw(
				_("Weekly Action Plan {0} belongs to project {1}, not {2}.").format(
					self.weekly_action_plan, wap.project, self.project
				)
			)

		if self.date and wap.from_date and wap.to_date:
			report_date = getdate(self.date)
			if report_date < getdate(wap.from_date) or report_date > getdate(wap.to_date):
				frappe.throw(
					_("Report date {0} must fall within the weekly plan period ({1} to {2}).").format(
						self.date, wap.from_date, wap.to_date
					)
				)

	def on_submit(self):
		self.update_project_expenses()
		self._refresh_linked_weekly_plan()

	def on_cancel(self):
		self.update_project_expenses()
		self._refresh_linked_weekly_plan()

	def _refresh_linked_weekly_plan(self):
		if not self.weekly_action_plan:
			return
		from construction_management.monitoring_and_evaluation.doctype.weekly_action_plan.weekly_action_plan import (
			update_weekly_plan_monitoring,
		)

		update_weekly_plan_monitoring(self.weekly_action_plan)

	def fetch_planned_targets(self):
		self.planned_revenue = 0.0
		self.planned_cost = 0.0
		self.planned_profit = 0.0

		if not self.weekly_action_plan:
			return

		wap = frappe.db.get_value(
			"Weekly Action Plan",
			self.weekly_action_plan,
			["total_revenue", "total_cost", "projected_profit", "from_date", "to_date"],
			as_dict=True,
		)
		if not wap:
			return

		working_days = self._get_working_days(wap.from_date, wap.to_date)
		self.planned_revenue = flt(wap.total_revenue) / working_days
		self.planned_cost = flt(wap.total_cost) / working_days
		self.planned_profit = flt(wap.projected_profit) / working_days

	def _get_working_days(self, from_date, to_date):
		if from_date and to_date:
			days = date_diff(getdate(to_date), getdate(from_date)) + 1
			return max(days, 1)
		return 7

	def fetch_daily_costs_data(self):
		if not self.project or not self.date:
			return

		self._fetch_labor_data()
		self._fetch_material_data()
		self._fetch_equipment_data()
		self._fetch_revenue()

	def _fetch_labor_data(self):
		labor_rows = frappe.db.sql(
			"""
			SELECT
				dcr.name as source_document,
				dcr.employee_type,
				COALESCE(dcr.total_salary, 0.0) as salary,
				COALESCE(dcr.total_ovettime_cost, 0.0) as overtime,
				(
					COALESCE(dcr.total_res_all, 0.0) +
					COALESCE(dcr.total_pr_all, 0.0) +
					COALESCE(dcr.total_prj_all, 0.0) +
					COALESCE(dcr.total_tr_all, 0.0) +
					COALESCE(dcr.total_hs_all, 0.0) +
					COALESCE(dcr.total_ptf, 0.0) +
					COALESCE(dcr.total_pt, 0.0)
				) as incentive
			FROM `tabDaily Cost Report` dcr
			WHERE dcr.project = %s AND dcr.date = %s AND dcr.docstatus = 1
			""",
			(self.project, self.date),
			as_dict=True,
		)

		self.labor_details = []
		self.direct_salary = 0.0
		self.direct_overtime = 0.0
		self.direct_incentive = 0.0
		self.indirect_salary = 0.0
		self.indirect_overtime = 0.0
		self.indirect_incentive = 0.0

		for row in labor_rows:
			total = flt(row.salary) + flt(row.overtime) + flt(row.incentive)
			self.append(
				"labor_details",
				{
					"source_document": row.source_document,
					"employee_type": row.employee_type,
					"salary": row.salary,
					"overtime": row.overtime,
					"incentive": row.incentive,
					"total_amount": total,
				},
			)

			if row.employee_type == "Daily Labour Employee":
				self.direct_salary += flt(row.salary)
				self.direct_overtime += flt(row.overtime)
				self.direct_incentive += flt(row.incentive)
			elif row.employee_type == "Employee":
				self.indirect_salary += flt(row.salary)
				self.indirect_overtime += flt(row.overtime)
				self.indirect_incentive += flt(row.incentive)

	def _fetch_material_data(self):
		stock_rows = frappe.db.sql(
			"""
			SELECT
				se.name as stock_entry,
				sed.item_code,
				i.item_name,
				sed.qty,
				sed.uom,
				sed.basic_rate as rate,
				COALESCE(sed.amount, 0.0) as amount,
				i.item_group,
				ig.parent_item_group,
				i.custom_subcategory
			FROM `tabStock Entry` se
			JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
			JOIN `tabItem` i ON i.name = sed.item_code
			LEFT JOIN `tabItem Group` ig ON ig.name = i.item_group
			WHERE se.project = %s AND se.posting_date = %s
				AND se.docstatus = 1 AND se.stock_entry_type = 'Material Issue'
			ORDER BY se.name, sed.idx
			""",
			(self.project, self.date),
			as_dict=True,
		)

		self.material_details = []
		self.material_fuel_cost = 0.0
		self.material_lubricant_cost = 0.0
		self.material_spare_parts_cost = 0.0
		self.material_construction_cost = 0.0

		for row in stock_rows:
			category = get_material_cost_category(
				row.item_group, row.parent_item_group, row.custom_subcategory
			)
			amount = flt(row.amount)

			self.append(
				"material_details",
				{
					"stock_entry": row.stock_entry,
					"item_code": row.item_code,
					"item_name": row.item_name,
					"qty": row.qty,
					"uom": row.uom,
					"rate": row.rate,
					"amount": amount,
					"cost_category": category,
				},
			)

			if category == "Fuel":
				self.material_fuel_cost += amount
			elif category == "Lubricant":
				self.material_lubricant_cost += amount
			elif category == "Spare Parts":
				self.material_spare_parts_cost += amount
			else:
				self.material_construction_cost += amount

	def _fetch_equipment_data(self):
		equipment_rows = frappe.db.sql(
			"""
			SELECT
				eer.name as source_document,
				eed.plate_number,
				eed.equipment_name,
				COALESCE(em.ownership_type, 'Own') as ownership_type,
				COALESCE(eed.current_op_expense, 0.0) as operating_expense,
				COALESCE(eed.current_idle_expense, 0.0) as idle_expense
			FROM `tabEquipment Expense Report` eer
			JOIN `tabEquipment Expense Detail` eed ON eed.parent = eer.name
			LEFT JOIN `tabEquipment Master` em ON em.name = eed.plate_number
			WHERE eer.project = %s AND %s BETWEEN eer.start_date AND eer.end_date
				AND eer.docstatus = 1
			ORDER BY eer.name, eed.idx
			""",
			(self.project, self.date),
			as_dict=True,
		)

		self.equipment_details = []
		self.equipment_own_direct = 0.0
		self.equipment_own_indirect = 0.0
		self.equipment_rental_direct = 0.0
		self.equipment_rental_indirect = 0.0
		self.equipment_fuel_own = 0.0
		self.equipment_fuel_rental = 0.0

		for row in equipment_rows:
			op_exp = flt(row.operating_expense)
			idle_exp = flt(row.idle_expense)
			total = op_exp + idle_exp

			self.append(
				"equipment_details",
				{
					"source_document": row.source_document,
					"plate_number": row.plate_number,
					"equipment_name": row.equipment_name,
					"ownership_type": row.ownership_type,
					"operating_expense": op_exp,
					"idle_expense": idle_exp,
					"total_expense": total,
				},
			)

			if row.ownership_type == "Rental":
				self.equipment_rental_direct += op_exp
				self.equipment_rental_indirect += idle_exp
			else:
				self.equipment_own_direct += op_exp
				self.equipment_own_indirect += idle_exp

	def _fetch_revenue(self):
		revenue_rows = frappe.db.sql(
			"""
			SELECT
				ts.name as timesheet,
				tsd.task,
				t.subject as activity,
				tsd.hours,
				tsd.billing_rate,
				COALESCE(tsd.billing_amount, 0.0) as billing_amount
			FROM `tabTimesheet` ts
			INNER JOIN `tabTimesheet Detail` tsd ON tsd.parent = ts.name
			LEFT JOIN `tabTask` t ON t.name = tsd.task
			WHERE tsd.project = %s AND DATE(tsd.from_time) = %s AND ts.docstatus = 1
			ORDER BY ts.name, tsd.idx
			""",
			(self.project, self.date),
			as_dict=True,
		)

		self.revenue_details = []
		self.revenue = 0.0
		for row in revenue_rows:
			amount = flt(row.billing_amount)
			self.revenue += amount
			self.append(
				"revenue_details",
				{
					"timesheet": row.timesheet,
					"task": row.task,
					"activity": row.activity,
					"hours": row.hours,
					"billing_rate": row.billing_rate,
					"billing_amount": amount,
				},
			)

	def calculate_totals(self):
		total_labor = (
			flt(self.direct_salary)
			+ flt(self.direct_overtime)
			+ flt(self.direct_incentive)
			+ flt(self.indirect_salary)
			+ flt(self.indirect_overtime)
			+ flt(self.indirect_incentive)
		)
		total_material = (
			flt(self.material_fuel_cost)
			+ flt(self.material_lubricant_cost)
			+ flt(self.material_spare_parts_cost)
			+ flt(self.material_construction_cost)
		)
		total_equipment = (
			flt(self.equipment_own_direct)
			+ flt(self.equipment_own_indirect)
			+ flt(self.equipment_rental_direct)
			+ flt(self.equipment_rental_indirect)
		)

		self.total_cost = total_labor + total_material + total_equipment
		self.profit_loss = flt(self.revenue) - self.total_cost

		self.variance_revenue = flt(self.revenue) - flt(self.planned_revenue)
		self.variance_cost = self.total_cost - flt(self.planned_cost)
		self.variance_profit = flt(self.profit_loss) - flt(self.planned_profit)

	def update_project_expenses(self):
		if not self.project:
			return

		aggregates = frappe.db.sql(
			"""
			SELECT
				SUM(COALESCE(direct_salary, 0.0)) as direct_salary,
				SUM(COALESCE(direct_overtime, 0.0)) as direct_overtime,
				SUM(COALESCE(direct_incentive, 0.0)) as direct_incentive,
				SUM(COALESCE(indirect_salary, 0.0)) as indirect_salary,
				SUM(COALESCE(indirect_overtime, 0.0)) as indirect_overtime,
				SUM(COALESCE(indirect_incentive, 0.0)) as indirect_incentive,
				SUM(COALESCE(material_fuel_cost, 0.0)) as material_fuel,
				SUM(COALESCE(material_lubricant_cost, 0.0)) as material_lubricant,
				SUM(COALESCE(material_spare_parts_cost, 0.0)) as material_spare,
				SUM(COALESCE(material_construction_cost, 0.0)) as material_construction,
				SUM(COALESCE(equipment_own_direct, 0.0)) as eq_own_direct,
				SUM(COALESCE(equipment_own_indirect, 0.0)) as eq_own_indirect,
				SUM(COALESCE(equipment_rental_direct, 0.0)) as eq_rental_direct,
				SUM(COALESCE(equipment_rental_indirect, 0.0)) as eq_rental_indirect,
				SUM(COALESCE(revenue, 0.0)) as total_revenue,
				SUM(COALESCE(total_cost, 0.0)) as total_cost,
				SUM(COALESCE(profit_loss, 0.0)) as total_profit
			FROM `tabDaily Resource Report`
			WHERE project = %s AND docstatus = 1
			""",
			(self.project,),
			as_dict=True,
		)

		data = aggregates[0] if aggregates else {}

		frappe.db.set_value(
			"Project",
			self.project,
			{
				"custom_salary_with_pension": data.get("direct_salary") or 0.0,
				"custom_overtime": data.get("direct_overtime") or 0.0,
				"custom_incentive": data.get("direct_incentive") or 0.0,
				"custom_salary_with_pension_i": data.get("indirect_salary") or 0.0,
				"custom_overtime_i": data.get("indirect_overtime") or 0.0,
				"custom_incentive_i": data.get("indirect_incentive") or 0.0,
				"custom_direct_lubricant_cost": data.get("material_lubricant") or 0.0,
				"custom_direct_spare_parts": data.get("material_spare") or 0.0,
				"custom__direct_material_cost": data.get("material_construction") or 0.0,
				"custom_own": data.get("eq_own_direct") or 0.0,
				"custom_own_i": data.get("eq_own_indirect") or 0.0,
				"custom_rental": data.get("eq_rental_direct") or 0.0,
				"custom_rental_i": data.get("eq_rental_indirect") or 0.0,
				"custom_f_own": data.get("material_fuel") or 0.0,
			},
			update_modified=True,
		)

	@frappe.whitelist()
	def fetch_totals(self):
		self.fetch_daily_costs_data()
		self.fetch_planned_targets()
		self.calculate_totals()
		return self._get_response_dict()

	def _get_response_dict(self):
		return {
			"planned_revenue": self.planned_revenue,
			"planned_cost": self.planned_cost,
			"planned_profit": self.planned_profit,
			"variance_revenue": self.variance_revenue,
			"variance_cost": self.variance_cost,
			"variance_profit": self.variance_profit,
			"direct_salary": self.direct_salary,
			"direct_overtime": self.direct_overtime,
			"direct_incentive": self.direct_incentive,
			"indirect_salary": self.indirect_salary,
			"indirect_overtime": self.indirect_overtime,
			"indirect_incentive": self.indirect_incentive,
			"material_fuel_cost": self.material_fuel_cost,
			"material_lubricant_cost": self.material_lubricant_cost,
			"material_spare_parts_cost": self.material_spare_parts_cost,
			"material_construction_cost": self.material_construction_cost,
			"equipment_own_direct": self.equipment_own_direct,
			"equipment_own_indirect": self.equipment_own_indirect,
			"equipment_rental_direct": self.equipment_rental_direct,
			"equipment_rental_indirect": self.equipment_rental_indirect,
			"total_cost": self.total_cost,
			"revenue": self.revenue,
			"profit_loss": self.profit_loss,
			"labor_details": self.labor_details,
			"material_details": self.material_details,
			"equipment_details": self.equipment_details,
			"revenue_details": self.revenue_details,
		}


@frappe.whitelist()
def get_weekly_plans_for_project(project, date=None):
	filters = {"project": project, "docstatus": 1}
	if date:
		filters["from_date"] = ["<=", date]
		filters["to_date"] = [">=", date]
	return frappe.get_all(
		"Weekly Action Plan",
		filters=filters,
		fields=["name", "from_date", "to_date", "weekly_no", "total_revenue", "total_cost"],
		order_by="from_date desc",
	)
