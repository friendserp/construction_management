# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"label": _("Item"),
			"fieldname": "agreement",
			"fieldtype": "Link",
			"options": "Subcontract Agreement",
			"width": 120
		},
		{
			"label": _("Type of Work"),
			"fieldname": "type_of_work",
			"fieldtype": "Small Text",
			"width": 150
		},
		{
			"label": _("Contractor"),
			"fieldname": "contractor",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Main Contract Amount"),
			"fieldname": "main_contract_amount",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Sub Contract Amount"),
			"fieldname": "sub_contract_amount",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Date of Contract Signed"),
			"fieldname": "agreement_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Agreement duration (Days)"),
			"fieldname": "duration",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Original Completion Date"),
			"fieldname": "end_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Advance Payment effected"),
			"fieldname": "advance_payment",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Advance payment effected %"),
			"fieldname": "advance_percent",
			"fieldtype": "Percent",
			"width": 100
		},
		{
			"label": _("Payment Prepared for sub contractor"),
			"fieldname": "payment_prepared",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Payment effected for main contractor"),
			"fieldname": "payment_effected_main",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Paid amount for sub contractor"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Balance"),
			"fieldname": "balance",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Time elapsed"),
			"fieldname": "time_elapsed",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Delay days"),
			"fieldname": "delay_days",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("% executed based on sub contract price"),
			"fieldname": "exec_sub",
			"fieldtype": "Percent",
			"width": 120
		},
		{
			"label": _("% based on main contract price"),
			"fieldname": "exec_main",
			"fieldtype": "Percent",
			"width": 120
		},
		{
			"label": _("% completed for sub contract"),
			"fieldname": "percent_completed",
			"fieldtype": "Percent",
			"width": 120
		}
	]

def get_data(filters):
	data = []
	
	query_filters = {}
	if filters.get("project"):
		query_filters["project"] = filters.get("project")
		
	agreements = frappe.get_all("Subcontract Agreement", 
		filters=query_filters,
		fields=["name", "type_of_work", "r_entity", "project", "total_price_with_vat", "agreement_date", "duration", "advance_amount", "advance_percent"]
	)
	
	for ag in agreements:
		# Fetch Main Contract Amount from Project
		project = frappe.get_cached_value("Project", ag.project, ["estimated_costing"])
		main_contract_amount = project[0] if project else 0
		
		# Fetch Payment Certificates (Submitted)
		certificates = frappe.get_all("Subcontract Payment Certificate",
			filters={"contract_agreement": ag.name, "docstatus": 1},
			fields=["total_with_vat", "net_payment"]
		)
		
		paid_amount = sum([c.net_payment for c in certificates])
		
		# Payment Prepared (Draft)
		payment_prepared_docs = frappe.get_all("Subcontract Payment Certificate",
			filters={"contract_agreement": ag.name, "docstatus": 0},
			fields=["net_payment"]
		)
		payment_prepared = sum([p.net_payment for p in payment_prepared_docs])
		
		balance = ag.total_price_with_vat - paid_amount
		
		# Time calculations using agreement_date
		time_elapsed = 0
		delay_days = 0
		end_date = None
		if ag.agreement_date:
			time_elapsed = frappe.utils.date_diff(frappe.utils.today(), ag.agreement_date)
			if ag.duration:
				end_date = frappe.utils.add_days(ag.agreement_date, ag.duration)
				if time_elapsed > ag.duration:
					delay_days = time_elapsed - ag.duration
				
		# % Executed
		exec_sub = (paid_amount / ag.total_price_with_vat * 100) if ag.total_price_with_vat else 0
		exec_main = (paid_amount / main_contract_amount * 100) if main_contract_amount else 0
		
		row = {
			"agreement": ag.name,
			"type_of_work": ag.type_of_work,
			"contractor": ag.r_entity,
			"main_contract_amount": main_contract_amount,
			"sub_contract_amount": ag.total_price_with_vat,
			"agreement_date": ag.agreement_date,
			"duration": ag.duration,
			"end_date": end_date,
			"advance_payment": ag.advance_amount,
			"advance_percent": ag.advance_percent,
			"payment_prepared": payment_prepared,
			"payment_effected_main": 0, # Placeholder
			"paid_amount": paid_amount,
			"balance": balance,
			"time_elapsed": time_elapsed,
			"delay_days": delay_days,
			"exec_sub": exec_sub,
			"exec_main": exec_main,
			"percent_completed": exec_sub
		}
		data.append(row)
		
	return data
