# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WeeklyActionPlan(Document):
	pass

@frappe.whitelist()
def get_cbd_details(task):
	"""
	Fetch Cost Break Down details for a given Task.
	Uses the 'cost_break_down' field on the Task document.
	"""
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
		"machinery": []
	}

	for m in cbd_doc.materials:
		resources["materials"].append({
			"item": m.item,
			"unit": m.unit,
			"consumption_rate": m.qty,
			"unit_price": m.rate
		})

	for m in cbd_doc.manpowers:
		resources["manpower"].append({
			"designation": m.labour,
			"no": m.no,
			"uf": m.uf,
			"cost_rate": m.indexed_hourly_cost
		})

	for m in cbd_doc.machineries:
		resources["machinery"].append({
			"equipment_type": m.type,
			"fuel_rate": m.fuel_rate if hasattr(m, 'fuel_rate') else 0,
			"rental_rate": m.hourly_rental
		})

	return resources
