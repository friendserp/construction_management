# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PriceEscalationClaim(Document):
	def validate(self):
		self.calculate_reinf()
		self.calculate_cement()
		self.calculate_fuel()
		self.update_summary()
		self.calculate_totals()

	def calculate_reinf(self):
		for row in self.reinf_details:
			row.net_qty = (row.total_work_qty or 0) - (row.prev_qty or 0)
			row.total_escalation_qty = row.net_qty * (row.qty_per_unit or 0)
			row.cost_variation = ( (row.current_price or 0) - (row.initial_price or 0) ) * row.total_escalation_qty

	def calculate_cement(self):
		for row in self.cement_details:
			row.net_qty = (row.total_work_qty or 0) - (row.prev_qty or 0)
			row.total_escalation_qty = row.net_qty * (row.qty_per_unit or 0)
			row.cost_variation = ( (row.current_price or 0) - (row.initial_price or 0) ) * row.total_escalation_qty

	def calculate_fuel(self):
		for row in self.fuel_details:
			if row.type == "Truck":
				row.total_fuel_consumed = (row.trip_distance or 0) * (row.fuel_per_km or 0) * (row.quantity or 0)
			else: # Machinery
				row.total_fuel_consumed = (row.consumption_per_hr or 0) * (row.quantity or 0)
			
			row.cost_variation = ( (row.current_price or 0) - (row.initial_price or 0) ) * row.total_fuel_consumed

	def update_summary(self):
		# Reset summary
		materials = {
			"Reinforcement bar": {"qty": 0, "unit": "Qt", "amount": 0},
			"Cement": {"qty": 0, "unit": "Bag", "amount": 0},
			"Fuel": {"qty": 0, "unit": "Lit", "amount": 0},
			"Asphalt": {"qty": 0, "unit": "Lit", "amount": 0}
		}

		# Sum from detail tables
		for row in self.reinf_details:
			materials["Reinforcement bar"]["qty"] += (row.total_escalation_qty or 0)
			materials["Reinforcement bar"]["amount"] += (row.cost_variation or 0)
			materials["Reinforcement bar"]["unit"] = row.unit or "Qt"

		for row in self.cement_details:
			materials["Cement"]["qty"] += (row.total_escalation_qty or 0)
			materials["Cement"]["amount"] += (row.cost_variation or 0)
			materials["Cement"]["unit"] = row.unit or "Bag"

		for row in self.fuel_details:
			materials["Fuel"]["qty"] += (row.total_fuel_consumed or 0)
			materials["Fuel"]["amount"] += (row.cost_variation or 0)
			materials["Fuel"]["unit"] = row.unit or "Lit"

		# Update or append summary items
		self.summary_items = []
		for material, data in materials.items():
			if data["amount"] != 0:
				self.append("summary_items", {
					"material": material,
					"total_quantity": data["qty"],
					"unit": data["unit"],
					"total_amount": data["amount"]
				})

	def calculate_totals(self):
		self.grand_total = sum([row.total_amount for row in self.summary_items])
		self.vat_amount = self.grand_total * 0.15
		self.total_with_vat = self.grand_total + self.vat_amount
