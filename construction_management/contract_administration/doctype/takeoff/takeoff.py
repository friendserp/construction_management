# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Takeoff(Document):
	def on_update(self):
		if not self.boq:
			return
		
		boq_items = frappe.get_all("BOQ Items", filters={"parent": self.boq}, fields=["name", "rate", "item_work"])
		boq_item_map = {item.item_work: item for item in boq_items}
		
		for takeoff_item in self.items:
			if takeoff_item.work_item and takeoff_item.work_item in boq_item_map:
				boq_item = boq_item_map[takeoff_item.work_item]
				frappe.db.set_value("BOQ Items", boq_item.name, "c_qty", takeoff_item.total_quantity)
				c_amount = (takeoff_item.total_quantity * boq_item.rate) if boq_item.rate else 0
				frappe.db.set_value("BOQ Items", boq_item.name, "c_amount", c_amount)
	
	def on_cancel(self):
		# Reset BOQ items when takeoff is cancelled
		if not self.boq:
			return
		
		boq_items = frappe.get_all("BOQ Items", filters={"parent": self.boq}, fields=["name", "item_work"])
		boq_item_map = {item.item_work: item for item in boq_items}
		
		for takeoff_item in self.items:
			if takeoff_item.work_item and takeoff_item.work_item in boq_item_map:
				boq_item = boq_item_map[takeoff_item.work_item]
				# Reset current quantities to 0
				frappe.db.set_value("BOQ Items", boq_item.name, "c_qty", 0)
				frappe.db.set_value("BOQ Items", boq_item.name, "c_amount", 0)