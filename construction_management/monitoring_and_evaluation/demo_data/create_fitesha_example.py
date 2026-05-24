# Copyright (c) 2026, Friends ERP and contributors
"""
Rich M&E demo for FITESHA TO SULULTA ROAD DEVELOPMENT PROJECT.

Run:
  bench --site <site> execute construction_management.monitoring_and_evaluation.demo_data.create_fitesha_example.create
"""

import frappe
from frappe.utils import add_days, flt, getdate

PROJECT = "FITESHA TO SULULTA ROAD DEVELOPMENT PROJECT"
EXAMPLE_FROM = "2026-05-19"
EXAMPLE_TO = "2026-05-25"
EXAMPLE_DATES = ["2026-05-21", "2026-05-22"]
PROTECTED_STOCK_ENTRIES = ["SIV-2026-00002"]
DEMO_EQUIPMENT_PREFIX = "DEMO-FS-"
DEMO_CBD_PREFIX = "DEMO-FS "

COMPANY = "Kushladder Construction PLC"
WAREHOUSE = "Furi Hana - KLC"
FUEL_ITEM = "14402-000-0001"


def create():
	frappe.only_for("System Manager")

	if not frappe.db.exists("Project", PROJECT):
		frappe.throw(f"Project not found: {PROJECT}")

	_cleanup_previous_example()
	cbd_map = _create_cost_breakdowns()
	equipment_names = _create_equipment_masters()
	_create_stock_entries()
	wap = _create_weekly_action_plan(cbd_map, equipment_names)
	_create_daily_cost_reports()
	_create_equipment_expense_report(equipment_names)

	from construction_management.monitoring_and_evaluation.timesheet_utils import (
		create_timesheets_from_weekly_plan,
	)

	timesheets = create_timesheets_from_weekly_plan(wap.name)
	drr_names = _create_daily_resource_reports(wap.name)

	from construction_management.monitoring_and_evaluation.doctype.weekly_action_plan.weekly_action_plan import (
		update_weekly_plan_monitoring,
	)

	update_weekly_plan_monitoring(wap.name)
	wap.reload()

	frappe.db.commit()

	result = {
		"weekly_action_plan": wap.name,
		"cost_breakdowns": list(cbd_map.values()),
		"equipment_masters": equipment_names,
		"timesheets_created": len(timesheets),
		"daily_resource_reports": drr_names,
		"planned_revenue": wap.total_revenue,
		"actual_revenue": wap.actual_revenue,
		"timesheet_lines_on_wap": len(wap.timesheet_entries or []),
	}

	print("\n=== Fitesha M&E Demo (full) ===")
	for k, v in result.items():
		print(f"  {k}: {v}")
	print(f"\nWeekly Plan: /app/weekly-action-plan/{wap.name}")
	for drr in drr_names:
		print(f"Daily Report: /app/daily-resource-report/{drr}")

	return result


def _cleanup_previous_example():
	for wap in frappe.get_all(
		"Weekly Action Plan",
		filters={"project": PROJECT, "from_date": EXAMPLE_FROM, "to_date": EXAMPLE_TO},
		pluck="name",
	):
		ts_names = frappe.get_all(
			"WAP Timesheet Plan", filters={"parent": wap}, pluck="timesheet"
		)
		for ts in set(filter(None, ts_names)):
			_cancel_delete("Timesheet", ts)

		frappe.db.delete("WAP Daily Summary", {"parent": wap})
		frappe.db.delete("WAP Timesheet Plan", {"parent": wap})

		for drr in frappe.get_all(
			"Daily Resource Report", filters={"weekly_action_plan": wap}, pluck="name"
		):
			frappe.db.set_value("Daily Resource Report", drr, "weekly_action_plan", None)
			_cancel_delete("Daily Resource Report", drr)

		_cancel_delete("Weekly Action Plan", wap)

	for dcr in frappe.get_all(
		"Daily Cost Report",
		filters={"project": PROJECT, "date": ["in", EXAMPLE_DATES]},
		pluck="name",
	):
		_cancel_delete("Daily Cost Report", dcr)

	for eer in frappe.get_all(
		"Equipment Expense Report",
		filters={"project": PROJECT, "start_date": EXAMPLE_FROM, "end_date": EXAMPLE_TO},
		pluck="name",
	):
		_cancel_delete("Equipment Expense Report", eer)

	for se in frappe.get_all(
		"Stock Entry",
		filters={
			"project": PROJECT,
			"posting_date": ["in", EXAMPLE_DATES],
			"stock_entry_type": "Material Issue",
		},
		pluck="name",
	):
		if se not in PROTECTED_STOCK_ENTRIES:
			_cancel_delete("Stock Entry", se)

	for em in frappe.get_all(
		"Equipment Master", filters={"equipment_code": ["like", f"{DEMO_EQUIPMENT_PREFIX}%"]}, pluck="name"
	):
		if frappe.db.exists("Equipment Master", em):
			frappe.delete_doc("Equipment Master", em, force=True, ignore_permissions=True)

	for cbd in frappe.get_all(
		"Cost Break Down", filters={"work_item": ["like", f"{DEMO_CBD_PREFIX}%"]}, pluck="name"
	):
		if frappe.db.exists("Cost Break Down", cbd):
			doc = frappe.get_doc("Cost Break Down", cbd)
			if doc.docstatus == 1:
				doc.cancel()
			doc.delete(ignore_permissions=True)


def _cancel_delete(doctype, name):
	if not name or not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus == 1:
		doc.cancel()
	if frappe.db.exists(doctype, name):
		doc.delete(ignore_permissions=True)


def _get_project_tasks(limit=3):
	return frappe.get_all(
		"Task",
		filters={"project": PROJECT},
		fields=["name", "subject"],
		order_by="creation desc",
		limit=limit,
	)


def _create_cost_breakdowns():
	"""CBD per task — used when building weekly plan activities."""
	tasks = _get_project_tasks(3)
	cbd_map = {}
	uom = "Meter"

	for task in tasks:
		work_item = f"{DEMO_CBD_PREFIX}{task.subject.strip()}"
		if frappe.db.exists("Cost Break Down", {"work_item": work_item}):
			cbd_name = frappe.db.get_value("Cost Break Down", {"work_item": work_item}, "name")
		else:
			cbd = frappe.new_doc("Cost Break Down")
			cbd.naming_series = "CBD-"
			cbd.work_item = work_item
			cbd.unit = uom
			cbd.productivity = 100
			cbd.direct_cost = 1200
			cbd.overhead_cost = 100
			cbd.profit_cost = 200
			cbd.total_unit_cost = 1500

			cbd.append(
				"materials",
				{
					"item": FUEL_ITEM,
					"unit": frappe.db.get_value("Item", FUEL_ITEM, "stock_uom") or "ltr",
					"qty": 5,
					"rate": 129.2,
				},
			)
			cbd.append(
				"manpowers",
				{"labour": "DL", "no": 2, "uf": 10, "indexed_hourly_cost": 150, "hourly_cost": 150},
			)
			cbd.append(
				"machineries",
				{"type": "Tools", "no": 1, "hourly_rental": 2500, "hourly_cost": 500},
			)
			cbd.insert(ignore_permissions=True)
			cbd.submit()
			cbd_name = cbd.name

		frappe.db.set_value("Task", task.name, "cost_break_down", cbd_name)
		cbd_map[task.name] = cbd_name

	return cbd_map


def _create_equipment_masters():
	"""Several own/rental machines on the Fitesha project."""
	specs = [
		{"plate": "EX-4525", "name": "Hitachi ZX350 Chain Excavator", "ownership": "Rental", "make": "HITACHI"},
		{"plate": "GR-0809", "name": "CAT 140H Motor Grader", "ownership": "Rental", "make": "CATERPILLAR"},
		{"plate": "DZ-0927", "name": "CAT D8R Bulldozer", "ownership": "Own", "make": "CATERPILLAR"},
		{"plate": "LD-2851", "name": "SEM 655D Wheel Loader", "ownership": "Own", "make": "SEM"},
		{"plate": "CM-1696", "name": "XCMG Single Drum Roller", "ownership": "Own", "make": "XCMG"},
		{"plate": "ET-3-A03916", "name": "SINOTRUK Dump Truck", "ownership": "Own", "make": "SINOTRUK"},
	]

	category = "Light Vehicles"
	sub_category = "Automobile"
	names = []

	for spec in specs:
		code = f"{DEMO_EQUIPMENT_PREFIX}{frappe.scrub(spec['plate'])}"
		if frappe.db.exists("Equipment Master", code):
			names.append(code)
			frappe.db.set_value("Equipment Master", code, "location", PROJECT)
			continue

		em = frappe.new_doc("Equipment Master")
		em.equipment_category = category
		em.equipment_sub_category = sub_category
		em.equipment_name = spec["name"]
		em.plate_number = spec["plate"]
		em.make = spec["make"]
		em.model = "DEMO"
		em.ownership_type = spec["ownership"]
		em.location = PROJECT
		em.equipment_code = code
		em.insert(ignore_permissions=True)
		names.append(em.name)

	return names


def _create_stock_entries():
	"""Material issues across demo dates (fuel and lubricants with known valuation)."""
	lubricant = frappe.db.get_value(
		"Item", {"custom_subcategory": "Oil and Lubricants"}, "name"
	)

	issues = [
		("2026-05-21", FUEL_ITEM, 500, 129.2),
		("2026-05-22", FUEL_ITEM, 320, 129.2),
	]
	if lubricant:
		issues.append(("2026-05-22", lubricant, 25, 890))

	for posting_date, item_code, qty, rate in issues:
		existing = frappe.get_all(
			"Stock Entry",
			filters={
				"project": PROJECT,
				"posting_date": posting_date,
				"docstatus": 1,
				"stock_entry_type": "Material Issue",
			},
			pluck="name",
		)
		if item_code == FUEL_ITEM and any(n in PROTECTED_STOCK_ENTRIES for n in existing):
			continue

		se = frappe.new_doc("Stock Entry")
		se.naming_series = "SIV-.YYYY.-"
		se.stock_entry_type = "Material Issue"
		se.purpose = "Material Issue"
		if frappe.get_meta("Stock Entry").has_field("custom_entry_type"):
			se.custom_entry_type = "Store Issue Voucher"
		se.company = COMPANY
		se.project = PROJECT
		if frappe.get_meta("Stock Entry").has_field("custom_project"):
			se.custom_project = PROJECT
		se.posting_date = posting_date
		se.from_warehouse = WAREHOUSE
		uom = frappe.db.get_value("Item", item_code, "stock_uom")
		se.append(
			"items",
			{
				"item_code": item_code,
				"qty": qty,
				"s_warehouse": WAREHOUSE,
				"uom": uom,
				"stock_uom": uom,
				"conversion_factor": 1,
				"basic_rate": rate,
				"allow_zero_valuation_rate": 1,
				"set_basic_rate_manually": 1,
				"project": PROJECT,
			},
		)
		se.insert(ignore_permissions=True)
		try:
			se.submit()
		except Exception:
			pass


def _create_weekly_action_plan(cbd_map, equipment_names):
	tasks = _get_project_tasks(2)
	if not tasks:
		frappe.throw(f"No tasks on {PROJECT}")

	wap = frappe.new_doc("Weekly Action Plan")
	wap.naming_series = "KLC-WAP-.YYYY.-.####."
	wap.project = PROJECT
	wap.weekly_no = 21
	wap.from_date = EXAMPLE_FROM
	wap.to_date = EXAMPLE_TO
	wap.daily_working_hours = 10
	wap.fuel_price = 129.2
	wap.overhead_percentage = 5

	total_revenue = 0.0
	total_cost = 0.0

	for idx, task in enumerate(tasks):
		qty = 80 if idx == 0 else 50
		unit_price = 1500
		expected = qty * unit_price
		total_revenue += expected

		row = wap.append(
			"action_plan_items",
			{
				"activity": task.name,
				"from_km": idx * 1.5,
				"to_km": (idx + 1) * 1.5,
				"qty": qty,
				"unit_price_share": unit_price,
				"expected_amount": expected,
			},
		)

		# Pull CBD resources (same as UI)
		from construction_management.monitoring_and_evaluation.doctype.weekly_action_plan.weekly_action_plan import (
			get_cbd_details,
		)

		cbd_data = get_cbd_details(task.name)
		if cbd_data:
			for m in cbd_data.get("materials", []):
				wap.append(
					"material_items",
					{
						"activity": task.name,
						"item": m["item"],
						"unit": m["unit"],
						"consumption_rate": m["consumption_rate"],
						"unit_price": m["unit_price"],
						"action_plan_item_name": row.name,
					},
				)
			for m in cbd_data.get("manpower", []):
				child = wap.append(
					"manpower_items",
					{
						"activity": task.name,
						"title": m["designation"],
						"no_of_workers": m["no"],
						"hours": m["uf"],
						"cost_rate": m["cost_rate"],
						"action_plan_item_name": row.name,
					},
				)
				child.total_hours = flt(child.no_of_workers) * flt(child.hours)
				child.amount = child.total_hours * flt(child.cost_rate)
				total_cost += flt(child.amount)

	if equipment_names:
		eq = equipment_names[0]
		wap.append(
			"equipment_items",
			{
				"activity": tasks[0].name,
				"total_hours": 40,
				"fuel_rate": 12,
				"rental_rate": 2800,
				"is_rental": 1,
				"total_cost": 40 * 12 * flt(wap.fuel_price) + 40 * 2800,
			},
		)

	for row in wap.material_items:
		qty = flt(row.consumption_rate) * flt(
			next((i.qty for i in wap.action_plan_items if i.activity == row.activity), 1)
		)
		row.total_qty = qty
		row.amount = qty * flt(row.unit_price)
		total_cost += flt(row.amount)

	for row in wap.equipment_items:
		total_cost += flt(row.total_cost)

	overhead = total_revenue * flt(wap.overhead_percentage) / 100
	wap.total_revenue = total_revenue
	wap.total_cost = total_cost
	wap.overhead_amount = overhead
	wap.projected_profit = total_revenue - total_cost - overhead

	wap.insert(ignore_permissions=True)
	wap.submit()
	return wap


def _create_daily_cost_reports():
	amounts = {
		"Daily Labour Employee": {"salary": 85000, "overtime": 12000, "incentive": 5000},
		"Employee": {"salary": 45000, "overtime": 3000, "incentive": 2000},
	}
	for report_date in EXAMPLE_DATES:
		for employee_type, vals in amounts.items():
			dcr = frappe.new_doc("Daily Cost Report")
			dcr.project = PROJECT
			dcr.date = report_date
			dcr.employee_type = employee_type
			dcr.total_salary = vals["salary"]
			dcr.total_ovettime_cost = vals["overtime"]
			dcr.total_res_all = vals["incentive"] / 2
			dcr.total_pr_all = vals["incentive"] / 2
			dcr.insert(ignore_permissions=True)
			dcr.submit()


def _create_equipment_expense_report(equipment_names):
	if not equipment_names:
		return None

	eer = frappe.new_doc("Equipment Expense Report")
	eer.naming_series = "KLC-EER-.YYYY.-.####."
	eer.project = PROJECT
	eer.start_date = EXAMPLE_FROM
	eer.end_date = EXAMPLE_TO

	for idx, eq in enumerate(equipment_names[:5]):
		meta = frappe.db.get_value(
			"Equipment Master",
			eq,
			["equipment_name", "ownership_type", "plate_number"],
			as_dict=True,
		)
		op = 18000 + idx * 2500
		idle = 4000 + idx * 500
		eer.append(
			"equipment_entries",
			{
				"plate_number": eq,
				"equipment_name": meta.equipment_name or eq,
				"current_op_hr": 8 + idx,
				"current_op_expense": op,
				"current_idle_expense": idle,
			},
		)

	eer.insert(ignore_permissions=True)
	eer.submit()
	return eer.name


def _create_daily_resource_reports(wap_name):
	names = []
	for report_date in EXAMPLE_DATES:
		drr = frappe.new_doc("Daily Resource Report")
		drr.naming_series = "KLC-DRR-.YYYY.-.####."
		drr.project = PROJECT
		drr.weekly_action_plan = wap_name
		drr.date = report_date
		drr.insert(ignore_permissions=True)
		drr.submit()
		names.append(drr.name)
	return names
