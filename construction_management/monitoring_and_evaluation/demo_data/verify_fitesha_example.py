# Copyright (c) 2026, Friends ERP and contributors
"""
Verify the Fitesha M&E example.

Run:
  bench --site <site> execute construction_management.monitoring_and_evaluation.demo_data.verify_fitesha_example.run
"""

import frappe
from frappe.utils import flt

from construction_management.monitoring_and_evaluation.demo_data.create_fitesha_example import (
	EXAMPLE_DATES,
	EXAMPLE_FROM,
	EXAMPLE_TO,
	PROJECT,
)


def run():
	frappe.connect()
	checks = []
	checks.append(_check("project_exists", _project_exists))
	checks.append(_check("weekly_plan_exists", _weekly_plan_exists))
	checks.append(_check("daily_reports_linked", _daily_reports_linked))
	checks.append(_check("material_from_stock_entry", _material_from_stock_entry))
	checks.append(_check("labor_from_daily_cost_report", _labor_from_daily_cost_report))
	checks.append(_check("plan_vs_actual_fields", _plan_vs_actual_fields))
	checks.append(_check("weekly_daily_summary_table", _weekly_daily_summary_table))
	checks.append(_check("revenue_on_may_22", _revenue_on_may_22))
	checks.append(_check("equipment_details_or_totals", _equipment_details_or_totals))
	checks.append(_check("revenue_timesheet_lines", _revenue_timesheet_lines))
	checks.append(_check("wap_timesheet_table", _wap_timesheet_table))
	checks.append(_check("multiple_material_stock_lines", _multiple_material_stock_lines))
	checks.append(_check("demo_equipment_masters", _demo_equipment_masters))

	passed = sum(1 for c in checks if c["ok"])
	failed = [c for c in checks if not c["ok"]]

	print("\n=== M&E Verification ===")
	for c in checks:
		status = "PASS" if c["ok"] else "FAIL"
		print(f"  [{status}] {c['name']}: {c['message']}")
	print(f"\n{passed}/{len(checks)} checks passed")

	if failed:
		frappe.throw(f"{len(failed)} verification check(s) failed")

	return {"passed": passed, "total": len(checks), "checks": checks}


def _check(name, fn):
	try:
		message = fn()
		return {"name": name, "ok": True, "message": message}
	except Exception as e:
		return {"name": name, "ok": False, "message": str(e)}


def _project_exists():
	if not frappe.db.exists("Project", PROJECT):
		raise AssertionError(f"Project missing: {PROJECT}")
	return PROJECT


def _weekly_plan_name():
	return frappe.db.get_value(
		"Weekly Action Plan",
		{"project": PROJECT, "from_date": EXAMPLE_FROM, "to_date": EXAMPLE_TO},
		"name",
	)


def _weekly_plan_exists():
	wap = _weekly_plan_name()
	if not wap:
		raise AssertionError("Weekly Action Plan not found — run create_fitesha_example first")
	wap_doc = frappe.get_doc("Weekly Action Plan", wap)
	if flt(wap_doc.total_revenue) <= 0:
		raise AssertionError("Planned revenue is zero")
	return wap


def _daily_reports_linked():
	wap = _weekly_plan_name()
	drrs = frappe.get_all(
		"Daily Resource Report",
		filters={"weekly_action_plan": wap, "docstatus": 1},
		pluck="name",
	)
	if len(drrs) < len(EXAMPLE_DATES):
		raise AssertionError(f"Expected {len(EXAMPLE_DATES)} DRRs, got {len(drrs)}")
	return ", ".join(drrs)


def _drr_for(date):
	wap = _weekly_plan_name()
	name = frappe.db.get_value(
		"Daily Resource Report", {"weekly_action_plan": wap, "date": date, "docstatus": 1}, "name"
	)
	if not name:
		raise AssertionError(f"No DRR for {date}")
	return frappe.get_doc("Daily Resource Report", name)


def _material_from_stock_entry():
	drr = _drr_for("2026-05-21")
	if not drr.material_details:
		raise AssertionError("No material detail rows")
	if not any(r.stock_entry == "SIV-2026-00002" for r in drr.material_details):
		raise AssertionError("Stock Entry SIV-2026-00002 not linked")
	return f"{len(drr.material_details)} material line(s), fuel cost {drr.material_fuel_cost}"


def _labor_from_daily_cost_report():
	drr = _drr_for("2026-05-21")
	if len(drr.labor_details) < 2:
		raise AssertionError("Expected at least 2 labor rows (direct + indirect)")
	if flt(drr.direct_salary) <= 0:
		raise AssertionError("Direct salary not aggregated")
	return f"{len(drr.labor_details)} labor rows, direct salary {drr.direct_salary}"


def _plan_vs_actual_fields():
	drr = _drr_for("2026-05-21")
	if flt(drr.planned_revenue) <= 0:
		raise AssertionError("Planned revenue not set")
	if drr.variance_profit is None:
		raise AssertionError("Variance profit missing")
	return f"planned {drr.planned_revenue}, actual revenue {drr.revenue}, variance {drr.variance_profit}"


def _weekly_daily_summary_table():
	wap = frappe.get_doc("Weekly Action Plan", _weekly_plan_name())
	wap.refresh_daily_summaries()
	if len(wap.daily_summaries) < len(EXAMPLE_DATES):
		raise AssertionError("Daily summary table incomplete")
	if flt(wap.actual_cost) <= 0:
		raise AssertionError("Week actual cost is zero")
	return f"{len(wap.daily_summaries)} rows, week actual cost {wap.actual_cost}"


def _revenue_on_may_22():
	drr = _drr_for("2026-05-22")
	if flt(drr.revenue) <= 0:
		raise AssertionError("Revenue from timesheets not pulled for 2026-05-22")
	return f"revenue {drr.revenue}"


def _revenue_timesheet_lines():
	drr = _drr_for("2026-05-22")
	if not drr.revenue_details:
		raise AssertionError("No timesheet revenue lines on daily report")
	if flt(drr.revenue) <= 0:
		raise AssertionError("Revenue total not from timesheets")
	return f"{len(drr.revenue_details)} timesheet line(s), total {drr.revenue}"


def _wap_timesheet_table():
	wap = frappe.get_doc("Weekly Action Plan", _weekly_plan_name())
	if len(wap.timesheet_entries or []) < 1:
		raise AssertionError("Weekly plan has no timesheet lines")
	return f"{len(wap.timesheet_entries)} timesheet row(s) on weekly plan"


def _multiple_material_stock_lines():
	drr = _drr_for("2026-05-22")
	if len(drr.material_details) < 1:
		raise AssertionError("Expected multiple material lines on 22 May")
	stock_entries = {r.stock_entry for r in drr.material_details}
	return f"{len(drr.material_details)} lines from {len(stock_entries)} stock issue(s)"


def _demo_equipment_masters():
	count = frappe.db.count("Equipment Master", {"equipment_code": ["like", "DEMO-FS-%"]})
	if count < 3:
		raise AssertionError(f"Expected demo equipment masters, found {count}")
	return f"{count} demo equipment master record(s)"


def _equipment_details_or_totals():
	drr = _drr_for("2026-05-21")
	eq_total = flt(drr.equipment_own_direct) + flt(drr.equipment_rental_direct)
	if drr.equipment_details:
		return f"{len(drr.equipment_details)} equipment row(s)"
	if eq_total > 0:
		return f"equipment cost totals {eq_total}"
	raise AssertionError("No equipment data on daily report")
