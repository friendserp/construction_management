# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SubcontractPaymentCertificate(Document):
	# Update the previous amount in BOQ tables and totals
	def on_submit(self):
		if not self.takeoff or not self.boq:
			return

		# Get takeoff items for this certificate
		tko_items = frappe.get_all("Takeoff Items", filters={"parent": self.takeoff}, fields=["work_item", "total_quantity"])
		
		# Get BOQ items
		boq_items = frappe.get_all("BOQ Items", filters={"parent": self.boq}, fields=["name", "item_work", "p_qty", "p_amount", "rate"])
		boq_item_map = {item.item_work: item for item in boq_items}
		
		# For each takeoff item, find its matching BOQ item and add to previous
		for tko_item in tko_items:
			if tko_item.work_item in boq_item_map:
				boq_item = boq_item_map[tko_item.work_item]
				tko_amount = tko_item.total_quantity * boq_item.rate
				
				# Add the current certificate's quantities to previous
				new_p_qty = (boq_item.p_qty or 0) + tko_item.total_quantity
				new_p_amount = (boq_item.p_amount or 0) + tko_amount
				
				# Update previous quantities and reset current quantities to 0
				frappe.db.set_value("BOQ Items", boq_item.name, {
					"p_qty": new_p_qty,
					"p_amount": new_p_amount,
					"c_qty": 0,
					"c_amount": 0
				})
	
	def on_cancel(self):
		if not self.takeoff or not self.boq:
			return

		# Get the takeoff items that were linked to this certificate
		tko_items = frappe.get_all("Takeoff Items", filters={"parent": self.takeoff}, fields=["work_item", "total_quantity"])
		
		# Get BOQ items
		boq_items = frappe.get_all("BOQ Items", filters={"parent": self.boq}, fields=["name", "item_work", "p_qty", "p_amount", "rate"])
		boq_item_map = {item.item_work: item for item in boq_items}
		
		# For each takeoff item, find its matching BOQ item and subtract the takeoff values from p_qty/p_amount
		for tko_item in tko_items:
			if tko_item.work_item in boq_item_map:
				boq_item = boq_item_map[tko_item.work_item]
				tko_amount = tko_item.total_quantity * boq_item.rate
				
				# Subtract the takeoff values from the previous quantities
				new_p_qty = (boq_item.p_qty or 0) - tko_item.total_quantity
				new_p_amount = (boq_item.p_amount or 0) - tko_amount
				
				# Update previous quantities and restore current quantities
				frappe.db.set_value("BOQ Items", boq_item.name, {
					"p_qty": new_p_qty,
					"p_amount": new_p_amount,
					"c_qty": new_p_qty, # This logic might need verification based on user flow
					"c_amount": new_p_amount
				})

@frappe.whitelist()
def get_certificate_data(contract_agreement):
	if not contract_agreement:
		return {}

	# Get contract info
	contract = frappe.get_doc("Subcontract Agreement", contract_agreement)
	
	# Get previous certificates
	previous_certificates = frappe.get_all(
		"Subcontract Payment Certificate",
		filters={"contract_agreement": contract_agreement, "docstatus": 1},
		fields=["name", "date", "net_payment"]
	)
	
	return {
		"contract": contract,
		"previous_certificates": previous_certificates
	}

@frappe.whitelist()
def get_payment_flow(docname):
	doc = frappe.get_doc("Subcontract Payment Certificate", docname)
	flow = []
	
	if doc.contract_agreement:
		flow.append({"label": "Subcontract Agreement", "id": doc.contract_agreement, "doctype": "Subcontract Agreement", "icon": "📄"})
	
	if doc.takeoff:
		flow.append({"label": "Takeoff", "id": doc.takeoff, "doctype": "Takeoff", "icon": "📊"})
	
	flow.append({"label": "Payment Certificate", "id": doc.name, "doctype": "Subcontract Payment Certificate", "icon": "💰", "current": True})
	
	return flow