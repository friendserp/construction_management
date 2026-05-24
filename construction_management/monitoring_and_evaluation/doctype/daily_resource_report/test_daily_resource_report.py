# Copyright (c) 2026, Friends ERP and Contributors

import unittest

import frappe
from frappe.utils import add_days, flt, getdate, today

from construction_management.monitoring_and_evaluation.doctype.daily_resource_report.daily_resource_report import (
	get_material_cost_category,
	get_weekly_plans_for_project,
)
from construction_management.monitoring_and_evaluation.project_monitoring import (
	get_project_monitoring_summary,
)


class TestDailyResourceReport(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.project = "_ME Test Project"
		if not frappe.db.exists("Project", cls.project):
			company = frappe.db.get_single_value("Global Defaults", "default_company")
			frappe.get_doc(
				{"doctype": "Project", "project_name": cls.project, "company": company}
			).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()

	def test_material_cost_category(self):
		self.assertEqual(get_material_cost_category("Gas oil", "", ""), "Fuel")
		self.assertEqual(get_material_cost_category("X", "", "Oil and Lubricants"), "Lubricant")
		self.assertEqual(get_material_cost_category("Spare Parts", "", ""), "Spare Parts")
		self.assertEqual(
			get_material_cost_category("Cement", "Construction Material", ""), "Construction Material"
		)

	def test_weekly_plan_date_validation(self):
		wap = self._make_wap()
		drr = frappe.new_doc("Daily Resource Report")
		drr.project = self.project
		drr.weekly_action_plan = wap.name
		drr.date = add_days(wap.from_date, -1)
		drr.naming_series = "KLC-DRR-.YYYY.-.####."
		with self.assertRaises(frappe.ValidationError):
			drr.insert(ignore_permissions=True)

	def test_planned_daily_targets_from_weekly_plan(self):
		wap = self._make_wap(total_revenue=70000, total_cost=35000, projected_profit=35000)
		drr = self._make_drr(wap, add_days(wap.from_date, 1))
		self.assertEqual(flt(drr.planned_revenue), flt(70000 / 7))
		self.assertEqual(flt(drr.planned_cost), flt(35000 / 7))

	def test_labor_detail_rows_from_daily_cost_report(self):
		wap = self._make_wap()
		report_date = add_days(wap.from_date, 2)
		self._make_dcr(report_date, "Daily Labour Employee", salary=10000, overtime=1000, incentive=500)
		drr = self._make_drr(wap, report_date)
		self.assertGreater(len(drr.labor_details), 0)
		self.assertEqual(flt(drr.direct_salary), 10000)
		self.assertEqual(flt(drr.direct_overtime), 1000)
		self.assertGreater(flt(drr.direct_incentive), 0)

	def test_fetch_totals_whitelisted(self):
		wap = self._make_wap()
		drr = self._make_drr(wap, add_days(wap.from_date, 3))
		result = drr.fetch_totals()
		self.assertIn("total_cost", result)
		self.assertIn("labor_details", result)

	def test_get_weekly_plans_for_project(self):
		wap = self._make_wap()
		plans = get_weekly_plans_for_project(self.project, date=add_days(wap.from_date, 1))
		self.assertTrue(any(p.name == wap.name for p in plans))

	def _make_wap(self, total_revenue=0, total_cost=0, projected_profit=0):
		from_date = getdate(today())
		to_date = add_days(from_date, 6)
		wap = frappe.new_doc("Weekly Action Plan")
		wap.naming_series = "KLC-WAP-.YYYY.-.####."
		wap.project = self.project
		wap.from_date = from_date
		wap.to_date = to_date
		wap.weekly_no = 99
		if total_revenue:
			wap.append(
				"action_plan_items",
				{"qty": 10, "unit_price_share": total_revenue / 10, "expected_amount": total_revenue},
			)
			wap.total_revenue = total_revenue
			wap.total_cost = total_cost
			wap.projected_profit = projected_profit
		wap.insert(ignore_permissions=True)
		if not total_revenue:
			frappe.db.set_value("Weekly Action Plan", wap.name, "total_revenue", 70000)
			frappe.db.set_value("Weekly Action Plan", wap.name, "total_cost", 35000)
			frappe.db.set_value("Weekly Action Plan", wap.name, "projected_profit", 35000)
		wap.reload()
		wap.submit()
		return wap

	def _make_dcr(self, report_date, employee_type, salary=0, overtime=0, incentive=0):
		dcr = frappe.new_doc("Daily Cost Report")
		dcr.project = self.project
		dcr.date = report_date
		dcr.employee_type = employee_type
		dcr.total_salary = salary
		dcr.total_ovettime_cost = overtime
		dcr.total_res_all = incentive
		dcr.insert(ignore_permissions=True)
		dcr.submit()
		return dcr

	def _make_drr(self, wap, report_date):
		drr = frappe.new_doc("Daily Resource Report")
		drr.naming_series = "KLC-DRR-.YYYY.-.####."
		drr.project = self.project
		drr.weekly_action_plan = wap.name
		drr.date = report_date
		drr.insert(ignore_permissions=True)
		return drr


class TestWeeklyActionPlanMonitoring(unittest.TestCase):
	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()

	def test_daily_summaries_after_drr_submit(self):
		frappe.set_user("Administrator")
		project = "_ME WAP Summary Project"
		if not frappe.db.exists("Project", project):
			frappe.get_doc(
				{
					"doctype": "Project",
					"project_name": project,
					"company": frappe.db.get_single_value("Global Defaults", "default_company"),
				}
			).insert(ignore_permissions=True)

		from_date = getdate(today())
		to_date = add_days(from_date, 6)
		wap = frappe.new_doc("Weekly Action Plan")
		wap.naming_series = "KLC-WAP-.YYYY.-.####."
		wap.project = project
		wap.from_date = from_date
		wap.to_date = to_date
		wap.insert(ignore_permissions=True)
		frappe.db.set_value("Weekly Action Plan", wap.name, "total_revenue", 100000)
		frappe.db.set_value("Weekly Action Plan", wap.name, "total_cost", 50000)

		report_date = add_days(from_date, 1)
		dcr = frappe.new_doc("Daily Cost Report")
		dcr.project = project
		dcr.date = report_date
		dcr.employee_type = "Daily Labour Employee"
		dcr.total_salary = 5000
		dcr.insert(ignore_permissions=True)
		dcr.submit()

		drr = frappe.new_doc("Daily Resource Report")
		drr.naming_series = "KLC-DRR-.YYYY.-.####."
		drr.project = project
		drr.weekly_action_plan = wap.name
		drr.date = report_date
		drr.insert(ignore_permissions=True)
		drr.submit()

		wap = frappe.get_doc("Weekly Action Plan", wap.name)
		wap.refresh_daily_summaries()
		self.assertEqual(len(wap.daily_summaries), 1)
		self.assertEqual(wap.daily_summaries[0].daily_resource_report, drr.name)
		self.assertGreater(flt(wap.actual_cost), 0)


class TestProjectMonitoring(unittest.TestCase):
	def test_project_monitoring_summary_returns_dict(self):
		frappe.set_user("Administrator")
		project = frappe.db.get_value("Project", {}, "name")
		self.assertTrue(project)
		summary = get_project_monitoring_summary(project)
		self.assertIn("actual_cost", summary)
		self.assertIn("planned_revenue", summary)
