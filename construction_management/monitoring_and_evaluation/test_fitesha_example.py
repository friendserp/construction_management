# Copyright (c) 2026, Friends ERP and Contributors
"""Verify the live Fitesha–Sululta M&E example after running create_fitesha_example."""

import unittest

import frappe
from frappe.utils import flt

from construction_management.monitoring_and_evaluation.demo_data.create_fitesha_example import (
	EXAMPLE_DATES,
	EXAMPLE_FROM,
	EXAMPLE_TO,
	PROJECT,
)


class TestFiteshaMEExample(unittest.TestCase):
	"""Run against site where create_fitesha_example was executed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Project", PROJECT):
			cls.skipTest(f"Project {PROJECT} not on this site")

		cls.wap = frappe.db.get_value(
			"Weekly Action Plan",
			{"project": PROJECT, "from_date": EXAMPLE_FROM, "to_date": EXAMPLE_TO},
			"name",
		)
		if not cls.wap:
			cls.skipTest("Run create_fitesha_example first")

	def test_weekly_action_plan_exists_with_plan_totals(self):
		wap = frappe.get_doc("Weekly Action Plan", self.wap)
		self.assertEqual(wap.project, PROJECT)
		self.assertGreater(flt(wap.total_revenue), 0)
		self.assertGreater(flt(wap.total_cost), 0)
		self.assertGreater(len(wap.action_plan_items), 0)

	def test_daily_resource_reports_linked(self):
		drrs = frappe.get_all(
			"Daily Resource Report",
			filters={"weekly_action_plan": self.wap, "docstatus": 1},
			fields=["name", "date", "total_cost", "revenue", "profit_loss"],
			order_by="date asc",
		)
		self.assertGreaterEqual(len(drrs), len(EXAMPLE_DATES))
		for d in EXAMPLE_DATES:
			self.assertTrue(any(str(r.date) == d for r in drrs), f"Missing DRR for {d}")

	def test_daily_report_has_material_lines_from_stock(self):
		drr = frappe.get_doc(
			"Daily Resource Report",
			{"weekly_action_plan": self.wap, "date": "2026-05-21"},
		)
		self.assertGreater(len(drr.material_details), 0)
		self.assertTrue(any(r.stock_entry == "SIV-2026-00002" for r in drr.material_details))

	def test_daily_report_has_labor_lines(self):
		drr = frappe.get_doc(
			"Daily Resource Report",
			{"weekly_action_plan": self.wap, "date": "2026-05-21"},
		)
		self.assertGreaterEqual(len(drr.labor_details), 2)
		self.assertGreater(flt(drr.direct_salary), 0)

	def test_plan_vs_actual_fields_populated(self):
		drr = frappe.get_doc(
			"Daily Resource Report",
			{"weekly_action_plan": self.wap, "date": "2026-05-21"},
		)
		self.assertGreater(flt(drr.planned_revenue), 0)
		self.assertGreater(flt(drr.planned_cost), 0)
		self.assertIsNotNone(drr.variance_profit)

	def test_weekly_plan_daily_summary_table(self):
		wap = frappe.get_doc("Weekly Action Plan", self.wap)
		wap.refresh_daily_summaries()
		self.assertGreaterEqual(len(wap.daily_summaries), len(EXAMPLE_DATES))
		self.assertGreater(flt(wap.actual_cost), 0)

	def test_revenue_from_timesheets_on_may_22(self):
		drr = frappe.get_doc(
			"Daily Resource Report",
			{"weekly_action_plan": self.wap, "date": "2026-05-22"},
		)
		self.assertGreater(flt(drr.revenue), 0)
