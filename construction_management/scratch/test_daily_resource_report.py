import frappe
from frappe.utils import getdate, add_to_date
import unittest

def run_tests():
	print("Starting Daily Resource Report Aggregation Integration Test...")
	
	# Helper to cancel and delete documents cleanly
	def clean_doctype(doctype, filters):
		docs = frappe.get_all(doctype, filters=filters, fields=["name", "docstatus"])
		for d in docs:
			if d.docstatus == 1:
				try:
					doc_obj = frappe.get_doc(doctype, d.name)
					doc_obj.cancel()
				except Exception:
					# Force docstatus to 2 via db if standard cancel fails
					frappe.db.set_value(doctype, d.name, "docstatus", 2)
			frappe.delete_doc(doctype, d.name, force=True)

	# 1. Setup clean test environment
	project_name = "DRR Test Project"
	clean_doctype("Daily Resource Report", {"project": project_name})
	clean_doctype("Daily Cost Report", {"project": project_name})
	clean_doctype("Stock Entry", {"project": project_name})
	clean_doctype("Equipment Expense Report", {"project": project_name})
	
	ts_details = frappe.get_all("Timesheet Detail", filters={"project": project_name}, fields=["parent"])
	for tsd in ts_details:
		clean_doctype("Timesheet", {"name": tsd.parent})

	if frappe.db.exists("Project", project_name):
		frappe.delete_doc("Project", project_name, force=True)

	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": project_name,
		"status": "Open"
	}).insert(ignore_permissions=True)
	
	test_date = "2026-05-22"
	
	if frappe.db.exists("Warehouse", "Central Warehouse - KLC"):
		frappe.db.set_value("Warehouse", "Central Warehouse - KLC", "disabled", 0)

	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)

	# 2. Mock Daily Cost Reports (Manpower)
	# Direct Labor
	dcr_direct = frappe.get_doc({
		"doctype": "Daily Cost Report",
		"project": project.name,
		"employee_type": "Daily Labour Employee",
		"date": test_date,
		"total_salary": 500.0,
		"total_ovettime_cost": 100.0,
		"total_res_all": 0.0,
		"total_pr_all": 0.0,
		"total_prj_all": 0.0,
		"total_tr_all": 0.0,
		"total_hs_all": 0.0,
		"total_ptf": 50.0,
		"total_pt": 50.0,
		"total_cost": 700.0,
		"employees": [
			{
				"employee_type": "Daily Labour Employee",
				"wage": 500.0,
				"daily_wage": 500.0,
				"total_overtime_cost": 100.0,
				"total_allowance_cost": 50.0,
				"total_perdium_cost": 50.0,
				"total_cost": 700.0
			}
		]
	}).insert(ignore_permissions=True)
	dcr_direct.submit()

	# Indirect Labor
	dcr_indirect = frappe.get_doc({
		"doctype": "Daily Cost Report",
		"project": project.name,
		"employee_type": "Employee",
		"date": test_date,
		"total_salary": 1000.0,
		"total_ovettime_cost": 200.0,
		"total_res_all": 50.0,
		"total_pr_all": 50.0,
		"total_prj_all": 50.0,
		"total_tr_all": 25.0,
		"total_hs_all": 25.0,
		"total_ptf": 0.0,
		"total_pt": 0.0,
		"total_cost": 1400.0,
		"employees": [
			{
				"employee_type": "Employee",
				"basic_salary": 1000.0,
				"daily_salary_rate": 1000.0,
				"total_overtime_cost": 200.0,
				"total_allowance_cost": 100.0,
				"total_perdium_cost": 100.0,
				"total_cost": 1400.0
			}
		]
	}).insert(ignore_permissions=True)
	dcr_indirect.submit()
	print("- Daily Cost Reports created and submitted.")

	# 3. Mock Stock Entry (Material)
	# Ensure item groups and items exist
	def ensure_item(item_code, item_group, parent_item_group="All Item Group", custom_subcategory=None):
		if not frappe.db.exists("Item Group", item_group):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": item_group,
				"parent_item_group": parent_item_group
			}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item Group", item_group, "parent_item_group", parent_item_group)

		if not frappe.db.exists("Item", item_code):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": item_group,
				"custom_subcategory": custom_subcategory,
				"stock_uom": "pcs",
				"is_stock_item": 1
			}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", item_code, {
				"item_group": item_group,
				"custom_subcategory": custom_subcategory
			})

	ensure_item("Diesel", "Gas oil")
	ensure_item("Engine Oil", "Lubricants", custom_subcategory="Oil and Lubricants")
	ensure_item("Filter", "Spare Parts")
	ensure_item("Sand", "Sands", parent_item_group="Construction Material")

	# Create Stock Receipt to populate warehouse and valuation rates
	receipt = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"custom_entry_type": "Transferred Goods Receiving Voucher",
		"posting_date": test_date,
		"set_posting_time": 1,
		"project": project.name,
		"items": [
			{"item_code": "Diesel", "qty": 100, "basic_rate": 80.0, "t_warehouse": "Central Warehouse - KLC"},
			{"item_code": "Engine Oil", "qty": 100, "basic_rate": 150.0, "t_warehouse": "Central Warehouse - KLC"},
			{"item_code": "Filter", "qty": 100, "basic_rate": 150.0, "t_warehouse": "Central Warehouse - KLC"},
			{"item_code": "Sand", "qty": 100, "basic_rate": 50.0, "t_warehouse": "Central Warehouse - KLC"}
		]
	}).insert(ignore_permissions=True)
	receipt.submit()

	# Create Stock Entry (Material Issue)
	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Issue",
		"custom_entry_type": "Store Issue Voucher",
		"posting_date": test_date,
		"set_posting_time": 1,
		"project": project.name,
		"items": [
			{"item_code": "Diesel", "item_group": "Gas oil", "qty": 10, "basic_rate": 80.0, "amount": 800.0, "s_warehouse": "Central Warehouse - KLC", "allow_zero_valuation_rate": 1},
			{"item_code": "Engine Oil", "item_group": "Lubricants", "qty": 2, "basic_rate": 150.0, "amount": 300.0, "s_warehouse": "Central Warehouse - KLC", "allow_zero_valuation_rate": 1},
			{"item_code": "Filter", "item_group": "Spare Parts", "qty": 1, "basic_rate": 150.0, "amount": 150.0, "s_warehouse": "Central Warehouse - KLC", "allow_zero_valuation_rate": 1},
			{"item_code": "Sand", "item_group": "Sands", "qty": 5, "basic_rate": 50.0, "amount": 250.0, "s_warehouse": "Central Warehouse - KLC", "allow_zero_valuation_rate": 1}
		]
	}).insert(ignore_permissions=True)
	se.submit()
	print("- Stock Entry created and submitted.")

	# 4. Mock Equipment Expense Report


	eer = frappe.get_doc({
		"doctype": "Equipment Expense Report",
		"project": project.name,
		"start_date": test_date,
		"end_date": test_date,
		"equipment_entries": [
			{
				"equipment_type": "Rental",
				"current_op_hr": 8.0,
				"current_id_hr": 2.0,
				"rental_rate_op": 100.0,
				"rental_rate_idle": 50.0
			},
			{
				"equipment_type": "Own",
				"current_op_hr": 8.0,
				"current_id_hr": 2.0,
				"rental_rate_op": 80.0,
				"rental_rate_idle": 40.0
			}
		]
	}).insert(ignore_permissions=True)
	eer.submit()
	print("- Equipment Expense Report created and submitted.")

	# 5. Mock Timesheet (Revenue)
	ts = frappe.get_doc({
		"doctype": "Timesheet",
		"time_logs": [
			{
				"project": project.name,
				"from_time": f"{test_date} 08:00:00",
				"to_time": f"{test_date} 17:00:00",
				"billing_amount": 5000.0,
				"billing_rate": 500.0,
				"hours": 9.0
			}
		]
	}).insert(ignore_permissions=True)
	ts.submit()
	print("- Timesheet created and submitted.")

	# 6. Create Daily Resource Report and verify aggregation
	drr = frappe.get_doc({
		"doctype": "Daily Resource Report",
		"project": project.name,
		"date": test_date
	})
	
	drr.insert(ignore_permissions=True)
	
	# Verify labor values
	# Daily Labour: base salary = 700 - 100 (OT) - 100 (allowance) = 500
	assert drr.direct_salary == 500.0, f"Expected 500, got {drr.direct_salary}"
	assert drr.direct_overtime == 100.0, f"Expected 100, got {drr.direct_overtime}"
	assert drr.direct_incentive == 100.0, f"Expected 100, got {drr.direct_incentive}"
	
	# Employee: base salary = 1400 - 200 (OT) - 200 (allowance) = 1000
	assert drr.indirect_salary == 1000.0, f"Expected 1000, got {drr.indirect_salary}"
	assert drr.indirect_overtime == 200.0, f"Expected 200, got {drr.indirect_overtime}"
	assert drr.indirect_incentive == 200.0, f"Expected 200, got {drr.indirect_incentive}"

	# Verify material values
	assert drr.material_fuel_cost == 800.0, f"Expected 800, got {drr.material_fuel_cost}"
	assert drr.material_lubricant_cost == 300.0, f"Expected 300, got {drr.material_lubricant_cost}"
	assert drr.material_spare_parts_cost == 150.0, f"Expected 150, got {drr.material_spare_parts_cost}"
	assert drr.material_construction_cost == 250.0, f"Expected 250, got {drr.material_construction_cost}"

	# Verify equipment values
	# Rental: op = 8 * 100 = 800; idle = 2 * 50 = 100
	assert drr.equipment_rental_direct == 800.0, f"Expected 800, got {drr.equipment_rental_direct}"
	assert drr.equipment_rental_indirect == 100.0, f"Expected 100, got {drr.equipment_rental_indirect}"
	
	# Own: op = 8 * 80 = 640; idle = 2 * 40 = 80
	assert drr.equipment_own_direct == 640.0, f"Expected 640, got {drr.equipment_own_direct}"
	assert drr.equipment_own_indirect == 80.0, f"Expected 80, got {drr.equipment_own_indirect}"

	# Verify revenue
	assert drr.revenue == 5000.0, f"Expected 5000, got {drr.revenue}"

	print("✔ Daily Resource Report fields verified successfully!")

	# 7. Submit Daily Resource Report and verify Project Update
	drr.submit()
	print("- Daily Resource Report submitted.")

	proj_updated = frappe.get_doc("Project", project.name)
	
	# Verify labor expense updated on project
	assert proj_updated.custom_salary_with_pension == 500.0
	assert proj_updated.custom_overtime == 100.0
	assert proj_updated.custom_incentive == 100.0
	assert proj_updated.custom_salary_with_pension_i == 1000.0
	assert proj_updated.custom_overtime_i == 200.0
	assert proj_updated.custom_incentive_i == 200.0

	# Verify material cost updated on project
	assert proj_updated.custom__direct_material_cost == 250.0
	assert proj_updated.custom_direct_lubricant_cost == 300.0
	assert proj_updated.custom_direct_spare_parts == 150.0

	# Verify equipment cost updated on project
	assert proj_updated.custom_own == 640.0
	assert proj_updated.custom_rental == 800.0
	assert proj_updated.custom_own_i == 80.0
	assert proj_updated.custom_rental_i == 100.0

	print("✔ Project Expense Details updated and verified successfully!")
	print("ALL TESTS PASSED SUCCESSFULLY! 100% CORRECT!")

if __name__ == "__main__":
	frappe.db.connect()
	run_tests()
