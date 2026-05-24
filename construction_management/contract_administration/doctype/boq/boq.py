# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BOQ(Document):
	def validate(self):
		self.update_summary()
		self.calculate_totals()

	def update_summary(self):
		if not self.items or not len(self.items):
			self.summary = []
			return

		summary_map = {}

		for item in self.items:
			task_group = item.task_group
			previous_amount = flt(item.p_amount)
			current_amount = flt(item.c_amount)
			total_amount = previous_amount + current_amount
			contract_amount = flt(item.amount)

			if not task_group:
				continue

			if task_group not in summary_map:
				summary_map[task_group] = {
					"task_group": task_group,
					"previous_amount": 0,
					"current_amount": 0,
					"todate_amount": 0,
					"contract_amount": 0,
				}

			summary_map[task_group]["previous_amount"] += previous_amount
			summary_map[task_group]["current_amount"] += current_amount
			summary_map[task_group]["todate_amount"] += total_amount
			summary_map[task_group]["contract_amount"] += contract_amount

		updated_summary = list(summary_map.values())

		self.summary = []

		for item in updated_summary:
			row = self.append("summary")
			row.task_group = item["task_group"]
			row.previous_amount = item["previous_amount"]
			row.current_amount = item["current_amount"]
			row.todate_amount = item["todate_amount"]
			row.contract_amount = item["contract_amount"]

	def calculate_totals(self):
		if not self.summary:
			return

		total_previous = 0
		total_current = 0
		total_todate = 0

		for row in self.summary:
			total_previous += flt(row.previous_amount)
			total_current += flt(row.current_amount)
			total_todate += flt(row.todate_amount)

		self.p_total = total_previous
		self.c_total = total_current
		self.t_total = total_todate

		self.p_vat = total_previous * 0.15
		self.c_vat = total_current * 0.15
		self.t_vat = total_todate * 0.15

		self.p_total_vat = total_previous * 1.15
		self.c_total_vat = total_current * 1.15
		self.t_total_vat = total_todate * 1.15
