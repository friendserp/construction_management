import frappe
import json
import os

def run():
	print("Importing custom doctypes...")
	
	base_path = os.path.join(frappe.get_app_path("construction_management"), "monitoring_and_evaluation", "doctype")
	
	doctypes = [
		"equipment_expense_detail/equipment_expense_detail.json",
		"equipment_expense_report/equipment_expense_report.json",
		"daily_resource_report/daily_resource_report.json"
	]
	
	for path in doctypes:
		full_path = os.path.join(base_path, path)
		if os.path.exists(full_path):
			with open(full_path, "r") as f:
				doc_data = json.load(f)
				doctype_name = doc_data.get("name")
				
				# If DocType exists, delete it first to ensure it's fully re-imported/updated
				if frappe.db.exists("DocType", doctype_name):
					# Temporarily disable developer_mode so delete_doc doesn't delete physical files
					is_dev = frappe.conf.get("developer_mode", 0)
					frappe.conf.developer_mode = 0
					try:
						frappe.delete_doc("DocType", doctype_name, force=True)
					finally:
						frappe.conf.developer_mode = is_dev
					print(f"- Existing DocType '{doctype_name}' deleted for clean import.")
				
				# Insert the DocType
				doc = frappe.get_doc(doc_data)
				doc.insert(ignore_permissions=True)
				print(f"✔ DocType '{doctype_name}' imported successfully!")
		else:
			print(f"❌ File not found: {full_path}")

	# Clear site cache and run DB sync
	frappe.clear_cache()
	print("- Site cache cleared.")

if __name__ == "__main__":
	frappe.db.connect()
	run()
