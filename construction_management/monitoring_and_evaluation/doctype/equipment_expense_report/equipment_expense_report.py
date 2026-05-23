# Copyright (c) 2026, Sami and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EquipmentExpenseReport(Document):
	def validate(self):
		self.calculate_expenses()

	def calculate_expenses(self):
		grand_total_prev = 0.0
		grand_total_current = 0.0
		grand_total_todate = 0.0

		for row in self.equipment_entries:
			# Calculate to-date hours
			row.todate_op_hr = (row.prev_op_hr or 0.0) + (row.current_op_hr or 0.0)
			row.todate_id_hr = (row.prev_id_hr or 0.0) + (row.current_id_hr or 0.0)
			row.todate_d_hr = (row.prev_d_hr or 0.0) + (row.current_d_hr or 0.0)
			row.todate_mob_hr = (row.prev_mob_hr or 0.0) + (row.current_mob_hr or 0.0)

			# Previous Period Expenses
			row.prev_op_expense = (row.prev_op_hr or 0.0) * (row.rental_rate_op or 0.0)
			row.prev_idle_expense = (row.prev_id_hr or 0.0) * (row.rental_rate_idle or 0.0)
			row.prev_total_expense = row.prev_op_expense + row.prev_idle_expense

			# Current Period Expenses
			row.current_op_expense = (row.current_op_hr or 0.0) * (row.rental_rate_op or 0.0)
			row.current_idle_expense = (row.current_id_hr or 0.0) * (row.rental_rate_idle or 0.0)
			row.current_total_expense = row.current_op_expense + row.current_idle_expense

			# To Date Expenses (Cumulative)
			row.todate_op_expense = row.prev_op_expense + row.current_op_expense
			row.todate_idle_expense = row.prev_idle_expense + row.current_idle_expense
			row.todate_total_expense = row.todate_op_expense + row.todate_idle_expense

			# Accumulate Grand Totals
			grand_total_prev += row.prev_total_expense
			grand_total_current += row.current_total_expense
			grand_total_todate += row.todate_total_expense

		self.grand_total_prev = grand_total_prev
		self.grand_total_current = grand_total_current
		self.grand_total_todate = grand_total_todate
