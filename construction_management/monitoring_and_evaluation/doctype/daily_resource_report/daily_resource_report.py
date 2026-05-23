# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

class DailyResourceReport(Document):
	def validate(self):
		self.fetch_daily_costs_data()
		self.calculate_totals()

	def on_submit(self):
		self.update_project_expenses()

	def on_cancel(self):
		self.update_project_expenses()

	def fetch_daily_costs_data(self):
		if not self.project or not self.date:
			return

		# 1. Fetch Labor Costs from Daily Cost Report
		labor_data = frappe.db.sql("""
			SELECT
				dcr.employee_type,
				SUM(COALESCE(dcr.total_salary, 0.0)) as salary,
				SUM(COALESCE(dcr.total_ovettime_cost, 0.0)) as overtime,
				SUM(
					COALESCE(dcr.total_res_all, 0.0) +
					COALESCE(dcr.total_pr_all, 0.0) +
					COALESCE(dcr.total_prj_all, 0.0) +
					COALESCE(dcr.total_tr_all, 0.0) +
					COALESCE(dcr.total_hs_all, 0.0) +
					COALESCE(dcr.total_ptf, 0.0) +
					COALESCE(dcr.total_pt, 0.0)
				) as incentive
			FROM
				`tabDaily Cost Report` dcr
			WHERE
				dcr.project = %s AND dcr.date = %s AND dcr.docstatus = 1
			GROUP BY
				dcr.employee_type
		""", (self.project, self.date), as_dict=True)

		# Reset labor fields
		self.direct_salary = 0.0
		self.direct_overtime = 0.0
		self.direct_incentive = 0.0
		self.indirect_salary = 0.0
		self.indirect_overtime = 0.0
		self.indirect_incentive = 0.0

		for row in labor_data:
			if row.employee_type == "Daily Labour Employee":
				self.direct_salary = row.salary or 0.0
				self.direct_overtime = row.overtime or 0.0
				self.direct_incentive = row.incentive or 0.0
			elif row.employee_type == "Employee":
				self.indirect_salary = row.salary or 0.0
				self.indirect_overtime = row.overtime or 0.0
				self.indirect_incentive = row.incentive or 0.0

		# 2. Fetch Material Costs from Stock Entries
		stock_data = frappe.db.sql("""
			SELECT
				i.item_group,
				ig.parent_item_group,
				i.custom_subcategory,
				SUM(COALESCE(sed.amount, 0.0)) as amount
			FROM
				`tabStock Entry` se
			JOIN
				`tabStock Entry Detail` sed ON sed.parent = se.name
			JOIN
				`tabItem` i ON i.name = sed.item_code
			LEFT JOIN
				`tabItem Group` ig ON ig.name = i.item_group
			WHERE
				se.project = %s AND se.posting_date = %s AND se.docstatus = 1 AND se.stock_entry_type = 'Material Issue'
			GROUP BY
				i.item_group, ig.parent_item_group, i.custom_subcategory
		""", (self.project, self.date), as_dict=True)

		# Reset material fields
		self.material_fuel_cost = 0.0
		self.material_lubricant_cost = 0.0
		self.material_spare_parts_cost = 0.0
		self.material_construction_cost = 0.0

		for row in stock_data:
			item_group = row.item_group or ""
			parent_item_group = row.parent_item_group or ""
			sub_cat = row.custom_subcategory or ""
			amount = row.amount or 0.0

			# 1. Fuel: item_group is Gas oil, Regular (Benzene), or Kerosene (Nechi Gas)
			if item_group in ["Gas oil", "Regular (Benzene)", "Kerosene (Nechi Gas)"]:
				self.material_fuel_cost += amount
			# 2. Lubricants: custom_subcategory is "Oil and Lubricants"
			elif sub_cat == "Oil and Lubricants":
				self.material_lubricant_cost += amount
			# 3. Spare Parts: item_group is "Spare Parts"
			elif item_group == "Spare Parts":
				self.material_spare_parts_cost += amount
			# 4. Construction: parent_item_group is "Construction Material"
			elif parent_item_group == "Construction Material":
				self.material_construction_cost += amount
			# Fallback
			else:
				self.material_construction_cost += amount

		# 3. Fetch Equipment Costs from Equipment Expense Report
		equipment_data = frappe.db.sql("""
			SELECT
				eed.equipment_type,
				SUM(COALESCE(eed.current_op_expense, 0.0)) as op_expense,
				SUM(COALESCE(eed.current_idle_expense, 0.0)) as idle_expense
			FROM
				`tabEquipment Expense Report` eer
			JOIN
				`tabEquipment Expense Detail` eed ON eed.parent = eer.name
			WHERE
				eer.project = %s AND %s BETWEEN eer.start_date AND eer.end_date AND eer.docstatus = 1
			GROUP BY
				eed.equipment_type
		""", (self.project, self.date), as_dict=True)

		# Reset equipment fields
		self.equipment_own_direct = 0.0
		self.equipment_own_indirect = 0.0
		self.equipment_rental_direct = 0.0
		self.equipment_rental_indirect = 0.0

		for row in equipment_data:
			eq_type = row.equipment_type or ""
			if eq_type == "Own":
				self.equipment_own_direct = row.op_expense or 0.0
				self.equipment_own_indirect = row.idle_expense or 0.0
			elif eq_type == "Rental":
				self.equipment_rental_direct = row.op_expense or 0.0
				self.equipment_rental_indirect = row.idle_expense or 0.0

		# 4. Fetch Revenue from Timesheets
		revenue_data = frappe.db.sql("""
			SELECT
				SUM(COALESCE(tsd.billing_amount, 0.0)) as billing_amount
			FROM
				`tabTimesheet` ts
			JOIN
				`tabTimesheet Detail` tsd ON tsd.parent = ts.name
			WHERE
				tsd.project = %s AND DATE(tsd.from_time) = %s AND ts.docstatus = 1
		""", (self.project, self.date))

		self.revenue = revenue_data[0][0] or 0.0

	def calculate_totals(self):
		total_labor = (
			(self.direct_salary or 0.0) + (self.direct_overtime or 0.0) + (self.direct_incentive or 0.0) +
			(self.indirect_salary or 0.0) + (self.indirect_overtime or 0.0) + (self.indirect_incentive or 0.0)
		)
		total_material = (
			(self.material_fuel_cost or 0.0) + (self.material_lubricant_cost or 0.0) +
			(self.material_spare_parts_cost or 0.0) + (self.material_construction_cost or 0.0)
		)
		total_equipment = (
			(self.equipment_own_direct or 0.0) + (self.equipment_own_indirect or 0.0) +
			(self.equipment_rental_direct or 0.0) + (self.equipment_rental_indirect or 0.0)
		)

		self.total_cost = total_labor + total_material + total_equipment
		self.profit_loss = (self.revenue or 0.0) - self.total_cost

	def update_project_expenses(self):
		if not self.project:
			return

		# Re-calculate cumulative expenses from all submitted Daily Resource Reports for the project
		aggregates = frappe.db.sql("""
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
				SUM(COALESCE(equipment_rental_indirect, 0.0)) as eq_rental_indirect
			FROM
				`tabDaily Resource Report`
			WHERE
				project = %s AND docstatus = 1
		""", (self.project,), as_dict=True)

		data = aggregates[0] if aggregates else {}

		# Update Project custom fields
		frappe.db.set_value("Project", self.project, {
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
			"custom_f_own": data.get("material_fuel") or 0.0
		}, update_modified=True)

	@frappe.whitelist()
	def fetch_totals(self):
		self.fetch_daily_costs_data()
		self.calculate_totals()
		return {
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
			"profit_loss": self.profit_loss
		}

