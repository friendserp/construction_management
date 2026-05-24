# Copyright (c) 2026, Friends ERP and contributors
"""Build and sync Construction Management workspaces."""

import json

import frappe

from construction_management.permissions import workspace_roles


def sync_all_workspaces():
	"""Push workspace definitions to the database."""
	for name, config in get_workspace_definitions().items():
		_sync_workspace(name, config)
	frappe.db.commit()


def get_workspace_definitions():
	return {
		"Construction Management": _construction_management_workspace(),
		"Bid": _bid_workspace(),
		"Contract Administration": _contract_administration_workspace(),
		"Monitoring and Evaluation": _monitoring_workspace(),
	}


def _sync_workspace(name, config):
	if frappe.db.exists("Workspace", name):
		doc = frappe.get_doc("Workspace", name)
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = name
		doc.label = config.get("label", name)
		doc.title = config.get("title", name)

	doc.type = "Workspace"

	for field in (
		"app",
		"module",
		"icon",
		"indicator_color",
		"parent_page",
		"sequence_id",
		"public",
		"hide_custom",
		"content",
	):
		if field in config:
			setattr(doc, field, config[field])

	doc.links = []
	for link in config.get("links", []):
		doc.append("links", link)

	doc.shortcuts = []
	for shortcut in config.get("shortcuts", []):
		doc.append("shortcuts", shortcut)

	doc.charts = []
	for chart in config.get("charts", []):
		doc.append("charts", chart)

	doc.number_cards = []
	for card in config.get("number_cards", []):
		doc.append("number_cards", card)

	doc.custom_blocks = []
	for block in config.get("custom_blocks", []):
		doc.append("custom_blocks", block)

	doc.quick_lists = []
	for quick_list in config.get("quick_lists", []):
		doc.append("quick_lists", quick_list)

	doc.roles = []
	for row in workspace_roles():
		doc.append("roles", row)

	doc.save(ignore_permissions=True)


def _content(blocks):
	return json.dumps(blocks)


def _construction_management_workspace():
	cards = [
		"Construction Projects",
		"Purchased Bids",
		"Active Subcontract Agreements",
		"Daily Report Profit",
	]
	erpnext_links = [
		_card_break("ERPNext Links"),
		_link("Timesheet"),
		_link("Stock Entry"),
	]
	if frappe.db.exists("DocType", "Equipment Master"):
		erpnext_links.append(_link("Equipment Master"))

	return {
		"app": "construction_management",
		"module": "Construction Management",
		"icon": "organization",
		"indicator_color": "blue",
		"parent_page": "",
		"sequence_id": 10,
		"public": 1,
		"hide_custom": 0,
		"charts": [{"chart_name": "Construction Project Trend", "label": "Construction Project Trend"}],
		"number_cards": [
			{"number_card_name": n, "label": n} for n in cards
		],
		"custom_blocks": [
			{"custom_block_name": "Construction Home Guide", "label": "Construction Home Guide"},
			{"custom_block_name": "Bid Process Flow", "label": "Bid Process Flow"},
			{"custom_block_name": "Contract Process Flow", "label": "Contract Process Flow"},
			{"custom_block_name": "Monitoring Process Flow", "label": "Monitoring Process Flow"},
		],
		"quick_lists": [
			{
				"document_type": "Project",
				"label": "Active Projects",
				"quick_list_filter": json.dumps({"status": ["=", "Open"]}),
			},
			{
				"document_type": "Bid Followup",
				"label": "Recent Bid Followups",
				"quick_list_filter": json.dumps(
					{"modified": ["Timespan", "last month"], "docstatus": ["!=", 2]}
				),
			},
			{
				"document_type": "Weekly Action Plan",
				"label": "This Week Action Plans",
				"quick_list_filter": json.dumps(
					{"from_date": ["Timespan", "this week"], "docstatus": ["<", 2]}
				),
			},
		],
		"content": _content(
			[
				_header("Construction Management"),
				_chart("Construction Project Trend", 12),
				_spacer("s0"),
				_custom_block("Construction Home Guide", 12),
				_spacer("s1"),
				_header("Key Metrics", level=4),
				_number_card("Construction Projects", 3),
				_number_card("Purchased Bids", 3),
				_number_card("Active Subcontract Agreements", 3),
				_number_card("Daily Report Profit", 3),
				_spacer("s2"),
				_header("Live Lists", level=4),
				_quick_list("Active Projects", 4),
				_quick_list("Recent Bid Followups", 4),
				_quick_list("This Week Action Plans", 4),
				_spacer("s3"),
				_header("Module Workflows", level=4),
				_custom_block("Bid Process Flow", 6),
				_custom_block("Contract Process Flow", 6),
				_spacer("s4"),
				_custom_block("Monitoring Process Flow", 12),
				_spacer("s5"),
				_header("Quick Access", level=4),
				_shortcut("Bid Module", 3),
				_shortcut("Contract Module", 3),
				_shortcut("Monitoring Module", 3),
				_shortcut("Project", 3),
				_spacer("s6"),
				_header("Dashboards", level=4),
				_shortcut("Construction Management Dashboard", 3),
				_shortcut("Bid Dashboard", 3),
				_shortcut("Contract Administration Dashboard", 3),
				_shortcut("Monitoring and Evaluation Dashboard", 3),
				_spacer("s7"),
				_card("Masters", 4),
				_card("Projects & Tasks", 4),
				_card("ERPNext Links", 4),
			]
		),
		"links": [
			_card_break("Masters"),
			_link("Consultant"),
			_link("Contractor Category"),
			_link("Subcontractor"),
			_card_break("Projects & Tasks"),
			_link("Project"),
			_link("Task"),
			_link("Customer"),
		]
		+ erpnext_links,
		"shortcuts": [
			_doctype_shortcut("Project"),
			_url_shortcut("Bid Module", "/app/bid"),
			_url_shortcut("Contract Module", "/app/contract-administration"),
			_url_shortcut("Monitoring Module", "/app/monitoring-and-evaluation"),
			_dashboard_shortcut("Construction Management Dashboard", "Construction Management"),
			_dashboard_shortcut("Bid Dashboard", "Bid"),
			_dashboard_shortcut("Contract Administration Dashboard", "Contract Administration"),
			_dashboard_shortcut(
				"Monitoring and Evaluation Dashboard", "Monitoring and Evaluation"
			),
		],
	}


def _bid_workspace():
	cards = ["Purchased Bids", "Open Bid Followups", "Submitted Cost Breakdowns"]
	return {
		"app": "construction_management",
		"module": "Bid",
		"icon": "file-text",
		"indicator_color": "blue",
		"parent_page": "Construction Management",
		"sequence_id": 11,
		"public": 1,
		"hide_custom": 0,
		"charts": [{"chart_name": "Bid Followup Trend", "label": "Bid Followup Trend"}],
		"number_cards": [{"number_card_name": n, "label": n} for n in cards],
		"custom_blocks": [
			{"custom_block_name": "Bid Process Flow", "label": "Bid Process Flow"},
		],
		"quick_lists": [
			{
				"document_type": "Bid Followup",
				"label": "Purchased Bids",
				"quick_list_filter": json.dumps({"status": ["=", "Purchased"]}),
			},
			{
				"document_type": "Bid Documentation Checklist",
				"label": "Pending Bid Checklists",
				"quick_list_filter": json.dumps({"docstatus": ["=", 0]}),
			},
			{
				"document_type": "Cost Break Down",
				"label": "Submitted Cost Breakdowns",
				"quick_list_filter": json.dumps({"docstatus": ["=", 1]}),
			},
		],
		"content": _content(
			[
				_header("Bid Management"),
				_chart("Bid Followup Trend", 12),
				_spacer("s0"),
				_custom_block("Bid Process Flow", 12),
				_spacer("s1"),
				_number_card("Purchased Bids", 4),
				_number_card("Open Bid Followups", 4),
				_number_card("Submitted Cost Breakdowns", 4),
				_spacer("s2"),
				_header("Live Lists", level=4),
				_quick_list("Purchased Bids", 4),
				_quick_list("Pending Bid Checklists", 4),
				_quick_list("Submitted Cost Breakdowns", 4),
				_spacer("s3"),
				_header("Quick Actions", level=4),
				_shortcut("Bid Followup", 3),
				_shortcut("Cost Break Down", 3),
				_shortcut("Bid Result", 3),
				_shortcut("Construction Hub", 3),
				_spacer("s4"),
				_card("Opportunity & Followup", 4),
				_card("Pre-Opening", 4),
				_card("Opening & Results", 4),
				_card("Estimating", 4),
				_card("Masters & Templates", 4),
			]
		),
		"links": [
			_card_break("Opportunity & Followup"),
			_link("Bid Followup"),
			_link("Detailed bid review"),
			_link("Site Visit Assessment"),
			_card_break("Pre-Opening"),
			_link("Bid Documentation Checklist"),
			_link("Bid Opening Followup"),
			_card_break("Opening & Results"),
			_link("Bid Opening Technical"),
			_link("Bid Opening Financial"),
			_link("Bid Result"),
			_link("Unqualified Bid Purchased"),
			_link("None Responsive Bid"),
			_card_break("Estimating"),
			_link("Cost Break Down"),
			_card_break("Masters & Templates"),
			_link("Bid Check list"),
			_link("Contractor Category"),
		],
		"shortcuts": [
			_doctype_shortcut("Bid Followup"),
			_doctype_shortcut("Cost Break Down"),
			_doctype_shortcut("Bid Result"),
			_url_shortcut("Construction Hub", "/app/construction-management"),
			_dashboard_shortcut("Bid Dashboard", "Bid"),
		],
	}


def _contract_administration_workspace():
	cards = [
		"Active Subcontract Agreements",
		"Submitted BOQs",
		"Payment Certificates",
		"Open Weekly Followups",
	]
	return {
		"app": "construction_management",
		"module": "Contract Administration",
		"icon": "briefcase",
		"indicator_color": "orange",
		"parent_page": "Construction Management",
		"sequence_id": 12,
		"public": 1,
		"hide_custom": 0,
		"charts": [
			{
				"chart_name": "Agreement Value by Project",
				"label": "Agreement Value by Project",
			}
		],
		"number_cards": [{"number_card_name": n, "label": n} for n in cards],
		"custom_blocks": [
			{"custom_block_name": "Contract Process Flow", "label": "Contract Process Flow"},
		],
		"quick_lists": [
			{
				"document_type": "BOQ",
				"label": "Submitted BOQs",
				"quick_list_filter": json.dumps({"docstatus": ["=", 1]}),
			},
			{
				"document_type": "Subcontract Agreement",
				"label": "Active Agreements",
				"quick_list_filter": json.dumps({"docstatus": ["=", 1]}),
			},
			{
				"document_type": "Subcontract Payment Certificate",
				"label": "Recent Payment Certificates",
				"quick_list_filter": json.dumps(
					{"modified": ["Timespan", "last month"], "docstatus": ["<", 2]}
				),
			},
			{
				"document_type": "Weekly Contractual Followup",
				"label": "Open Weekly Followups",
				"quick_list_filter": json.dumps({"docstatus": ["=", 0]}),
			},
		],
		"content": _content(
			[
				_header("Contract Administration"),
				_chart("Agreement Value by Project", 12),
				_spacer("s0"),
				_custom_block("Contract Process Flow", 12),
				_spacer("s1"),
				_number_card("Active Subcontract Agreements", 3),
				_number_card("Submitted BOQs", 3),
				_number_card("Payment Certificates", 3),
				_number_card("Open Weekly Followups", 3),
				_spacer("s2"),
				_header("Live Lists", level=4),
				_quick_list("Submitted BOQs", 3),
				_quick_list("Active Agreements", 3),
				_quick_list("Recent Payment Certificates", 3),
				_quick_list("Open Weekly Followups", 3),
				_spacer("s3"),
				_header("Quick Actions", level=4),
				_shortcut("BOQ", 3),
				_shortcut("Subcontract Agreement", 3),
				_shortcut("Takeoff", 3),
				_shortcut("Construction Hub", 3),
				_spacer("s4"),
				_card("Agreements & BOQ", 4),
				_card("Measurements & Payments", 4),
				_card("Followups & Bonds", 4),
				_card("Claims & Extensions", 4),
				_card("Variations & Escalation", 4),
			]
		),
		"links": [
			_card_break("Agreements & BOQ"),
			_link("BOQ"),
			_link("Subcontract Agreement"),
			_link("Takeoff"),
			_card_break("Measurements & Payments"),
			_link("Subcontract Payment Certificate"),
			_link("List of Work"),
			_card_break("Followups & Bonds"),
			_link("Weekly Contractual Followup"),
			_link("Contractual Followup Summary"),
			_link("Performance Bond Followup"),
			_link("Contract Time Followup"),
			_card_break("Claims & Extensions"),
			_link("Claim Event Detail"),
			_link("Time Extension Claim"),
			_link("Delay Justification"),
			_link("Price Escalation Claim"),
			_card_break("Variations & Escalation"),
			_link("Project Variation"),
			_link("Subcontractor Selection Criteria"),
			_link("Subcontractor Criteria"),
		],
		"shortcuts": [
			_doctype_shortcut("BOQ"),
			_doctype_shortcut("Subcontract Agreement"),
			_doctype_shortcut("Takeoff"),
			_url_shortcut("Construction Hub", "/app/construction-management"),
			_dashboard_shortcut("Contract Administration Dashboard", "Contract Administration"),
		],
	}


def _monitoring_workspace():
	cards = [
		"Weekly Action Plans",
		"Daily Resource Reports",
		"Daily Report Profit",
		"Daily Report Cost",
	]
	return {
		"app": "construction_management",
		"module": "Monitoring and Evaluation",
		"icon": "trending-up",
		"indicator_color": "green",
		"parent_page": "Construction Management",
		"sequence_id": 13,
		"public": 1,
		"hide_custom": 0,
		"charts": [
			{"chart_name": "Daily Resource Reports Trend", "label": "Daily Resource Reports Trend"},
			{"chart_name": "Profit vs Cost Trend", "label": "Profit vs Cost Trend"},
		],
		"number_cards": [{"number_card_name": n, "label": n} for n in cards],
		"custom_blocks": [
			{"custom_block_name": "Monitoring Process Flow", "label": "Monitoring Process Flow"},
		],
		"quick_lists": [
			{
				"document_type": "Weekly Action Plan",
				"label": "This Week Plans",
				"quick_list_filter": json.dumps(
					{"from_date": ["Timespan", "this week"], "docstatus": ["<", 2]}
				),
			},
			{
				"document_type": "Daily Resource Report",
				"label": "Recent Daily Reports",
				"quick_list_filter": json.dumps(
					{"date": ["Timespan", "this month"], "docstatus": ["=", 1]}
				),
			},
			{
				"document_type": "Equipment Expense Report",
				"label": "Equipment Reports",
				"quick_list_filter": json.dumps(
					{"modified": ["Timespan", "last month"], "docstatus": ["<", 2]}
				),
			},
		],
		"content": _content(
			[
				_header("Monitoring & Evaluation"),
				_chart("Daily Resource Reports Trend", 6),
				_chart("Profit vs Cost Trend", 6),
				_spacer("s0"),
				_custom_block("Monitoring Process Flow", 12),
				_spacer("s1"),
				_number_card("Weekly Action Plans", 3),
				_number_card("Daily Resource Reports", 3),
				_number_card("Daily Report Profit", 3),
				_number_card("Daily Report Cost", 3),
				_spacer("s2"),
				_header("Live Lists", level=4),
				_quick_list("This Week Plans", 4),
				_quick_list("Recent Daily Reports", 4),
				_quick_list("Equipment Reports", 4),
				_spacer("s3"),
				_header("Quick Actions", level=4),
				_shortcut("Weekly Action Plan", 3),
				_shortcut("Daily Resource Report", 3),
				_shortcut("Equipment Expense Report", 3),
				_shortcut("Construction Hub", 3),
				_spacer("s4"),
				_card("Weekly Planning", 4),
				_card("Daily Monitoring", 4),
				_card("Cost & Equipment", 4),
				_card("ERPNext Sources", 4),
			]
		),
		"links": [
			_card_break("Weekly Planning"),
			_link("Weekly Action Plan"),
			_card_break("Daily Monitoring"),
			_link("Daily Resource Report"),
			_card_break("Cost & Equipment"),
			_link("Equipment Expense Report"),
			_card_break("ERPNext Sources"),
			_link("Project"),
			_link("Task"),
			_link("Timesheet"),
			_link("Stock Entry"),
		],
		"shortcuts": [
			_doctype_shortcut("Weekly Action Plan"),
			_doctype_shortcut("Daily Resource Report"),
			_doctype_shortcut("Equipment Expense Report"),
			_url_shortcut("Construction Hub", "/app/construction-management"),
			_dashboard_shortcut(
				"Monitoring and Evaluation Dashboard", "Monitoring and Evaluation"
			),
		],
	}


# --- content block helpers ---


def _header(text, level=3, uid=None):
	tag = "h3" if level == 3 else "h4"
	return {
		"id": uid or frappe.scrub(text)[:20],
		"type": "header",
		"data": {"text": f'<span class="{tag}"><b>{text}</b></span>', "col": 12},
	}


def _spacer(uid):
	return {"id": uid, "type": "spacer", "data": {"col": 12}}


def _chart(name, col):
	return {
		"id": frappe.scrub(name),
		"type": "chart",
		"data": {"chart_name": name, "col": col},
	}


def _number_card(name, col):
	return {
		"id": frappe.scrub(name)[:30],
		"type": "number_card",
		"data": {"number_card_name": name, "col": col},
	}


def _custom_block(name, col):
	return {
		"id": frappe.scrub(name)[:30],
		"type": "custom_block",
		"data": {"custom_block_name": name, "col": col},
	}


def _quick_list(name, col):
	return {
		"id": frappe.scrub(name)[:30],
		"type": "quick_list",
		"data": {"quick_list_name": name, "col": col},
	}


def _shortcut(name, col):
	return {
		"id": frappe.scrub(name)[:30],
		"type": "shortcut",
		"data": {"shortcut_name": name, "col": col},
	}


def _card(name, col):
	return {
		"id": frappe.scrub(name)[:30],
		"type": "card",
		"data": {"card_name": name, "col": col},
	}


def _card_break(label):
	return {
		"hidden": 0,
		"is_query_report": 0,
		"label": label,
		"link_count": 0,
		"link_type": "DocType",
		"onboard": 0,
		"type": "Card Break",
	}


def _link(link_to, link_type="DocType"):
	return {
		"hidden": 0,
		"is_query_report": 0,
		"label": link_to,
		"link_count": 0,
		"link_to": link_to,
		"link_type": link_type,
		"onboard": 0,
		"type": "Link",
	}


def _doctype_shortcut(label):
	return {"label": label, "link_to": label, "type": "DocType"}


def _url_shortcut(label, url):
	return {"label": label, "type": "URL", "url": url}


def _dashboard_shortcut(label, link_to):
	return {"label": label, "link_to": link_to, "type": "Dashboard"}
