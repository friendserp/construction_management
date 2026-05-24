# Copyright (c) 2026, Friends ERP and contributors

import json

import frappe
from frappe import _


def setup_all():
	"""Create dashboard assets, sync workspaces, permissions, and export fixtures."""
	cleanup_legacy_assets()
	create_number_cards()
	create_custom_blocks()
	create_dashboard_charts()
	create_dashboards()
	sync_workspaces()
	setup_project_user_permissions()
	export_workspaces()
	frappe.db.commit()


def setup_project_user_permissions():
	from construction_management.permissions import setup_all as setup_perms

	setup_perms()


def cleanup_legacy_assets():
	"""Remove old CM-prefixed dashboard assets."""
	for doctype, names in (
		(
			"Number Card",
			(
				"CM Total Projects",
				"CM Purchased Bids",
				"CM Active Agreements",
				"CM Weekly Action Plans",
				"CM Actual Profit",
				"CM Actual Cost",
				"Total Projects-1",
				"Purchased Bids-1",
				"Active Agreements-1",
			),
		),
		(
			"Custom HTML Block",
			(
				"CM Quick Stats",
				"CM Bid Overview",
				"CM Contract Overview",
				"CM Monitoring Overview",
			),
		),
		(
			"Dashboard Chart",
			(
				"CM Project Count Trend",
				"CM Bid Followup Trend",
				"CM Agreement Value by Project",
				"CM Daily Reports Trend",
				"CM Profit vs Cost Trend",
				"Profit vs Cost",
			),
		),
		(
			"Number Card",
			(
				"Total Projects",
				"Total Actual Cost",
				"Total Actual Profit",
				"Actual Cost",
				"Actual Profit",
				"Active Agreements",
			),
		),
	):
		for name in names:
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=1)

	frappe.db.commit()


def create_number_cards():
	cards = [
		{
			"name": "Construction Projects",
			"label": "Construction Projects",
			"type": "Document Type",
			"document_type": "Project",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Construction Management",
			"filters_json": "[]",
			"dynamic_filters_json": "",
			"color": "#2490ef",
		},
		{
			"name": "Purchased Bids",
			"label": "Purchased Bids",
			"type": "Document Type",
			"document_type": "Bid Followup",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Bid",
			"filters_json": json.dumps([["Bid Followup", "status", "=", "Purchased"]]),
			"dynamic_filters_json": "",
			"color": "#30a66d",
		},
		{
			"name": "Open Bid Followups",
			"label": "Open Bid Followups",
			"type": "Document Type",
			"document_type": "Bid Followup",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Bid",
			"filters_json": json.dumps([["Bid Followup", "status", "!=", "Purchased"]]),
			"dynamic_filters_json": "",
			"color": "#5e64ff",
		},
		{
			"name": "Submitted Cost Breakdowns",
			"label": "Submitted Cost Breakdowns",
			"type": "Document Type",
			"document_type": "Cost Break Down",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Bid",
			"filters_json": json.dumps([["Cost Break Down", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#ffa00a",
		},
		{
			"name": "Active Subcontract Agreements",
			"label": "Active Subcontract Agreements",
			"type": "Document Type",
			"document_type": "Subcontract Agreement",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Contract Administration",
			"filters_json": json.dumps([["Subcontract Agreement", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#e86c13",
		},
		{
			"name": "Submitted BOQs",
			"label": "Submitted BOQs",
			"type": "Document Type",
			"document_type": "BOQ",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Contract Administration",
			"filters_json": json.dumps([["BOQ", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#2490ef",
		},
		{
			"name": "Payment Certificates",
			"label": "Payment Certificates",
			"type": "Document Type",
			"document_type": "Subcontract Payment Certificate",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Contract Administration",
			"filters_json": json.dumps([["Subcontract Payment Certificate", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#28a745",
		},
		{
			"name": "Open Weekly Followups",
			"label": "Open Weekly Followups",
			"type": "Document Type",
			"document_type": "Weekly Contractual Followup",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Contract Administration",
			"filters_json": json.dumps([["Weekly Contractual Followup", "docstatus", "=", 0]]),
			"dynamic_filters_json": "",
			"color": "#ff5858",
		},
		{
			"name": "Weekly Action Plans",
			"label": "Weekly Action Plans",
			"type": "Document Type",
			"document_type": "Weekly Action Plan",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Monitoring and Evaluation",
			"filters_json": json.dumps([["Weekly Action Plan", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#5e64ff",
		},
		{
			"name": "Daily Resource Reports",
			"label": "Daily Resource Reports",
			"type": "Document Type",
			"document_type": "Daily Resource Report",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Monitoring and Evaluation",
			"filters_json": json.dumps([["Daily Resource Report", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#2490ef",
		},
		{
			"name": "Daily Report Profit",
			"label": "Daily Report Profit",
			"type": "Document Type",
			"document_type": "Daily Resource Report",
			"function": "Sum",
			"aggregate_function_based_on": "profit_loss",
			"is_public": 1,
			"is_standard": 1,
			"module": "Monitoring and Evaluation",
			"filters_json": json.dumps([["Daily Resource Report", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#28a745",
		},
		{
			"name": "Daily Report Cost",
			"label": "Daily Report Cost",
			"type": "Document Type",
			"document_type": "Daily Resource Report",
			"function": "Sum",
			"aggregate_function_based_on": "total_cost",
			"is_public": 1,
			"is_standard": 1,
			"module": "Monitoring and Evaluation",
			"filters_json": json.dumps([["Daily Resource Report", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"color": "#ff5858",
		},
	]
	for card in cards:
		_upsert_number_card(card)
	frappe.db.commit()


def create_dashboard_charts():
	charts = [
		{
			"chart_name": "Construction Project Trend",
			"chart_type": "Count",
			"document_type": "Project",
			"type": "Line",
			"timeseries": 1,
			"timespan": "Last Year",
			"time_interval": "Monthly",
			"based_on": "creation",
			"filters_json": "[]",
			"dynamic_filters_json": "",
			"is_public": 1,
			"is_standard": 1,
			"module": "Construction Management",
			"color": "#2490ef",
		},
		{
			"chart_name": "Bid Followup Trend",
			"chart_type": "Count",
			"document_type": "Bid Followup",
			"type": "Bar",
			"timeseries": 1,
			"timespan": "Last Quarter",
			"time_interval": "Monthly",
			"based_on": "creation",
			"filters_json": "[]",
			"dynamic_filters_json": "",
			"is_public": 1,
			"is_standard": 1,
			"module": "Bid",
			"color": "#2490ef",
		},
		{
			"chart_name": "Agreement Value by Project",
			"chart_type": "Group By",
			"document_type": "Subcontract Agreement",
			"type": "Bar",
			"group_by_type": "Sum",
			"group_by_based_on": "project",
			"aggregate_function_based_on": "total_price_with_vat",
			"filters_json": json.dumps([["Subcontract Agreement", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"is_public": 1,
			"is_standard": 1,
			"module": "Contract Administration",
			"color": "#e86c13",
		},
		{
			"chart_name": "Daily Resource Reports Trend",
			"chart_type": "Count",
			"document_type": "Daily Resource Report",
			"type": "Line",
			"timeseries": 1,
			"timespan": "Last Quarter",
			"time_interval": "Weekly",
			"based_on": "creation",
			"filters_json": json.dumps([["Daily Resource Report", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"is_public": 1,
			"is_standard": 1,
			"module": "Monitoring and Evaluation",
			"color": "#5e64ff",
		},
		{
			"chart_name": "Profit vs Cost Trend",
			"chart_type": "Sum",
			"document_type": "Daily Resource Report",
			"type": "Line",
			"timeseries": 1,
			"timespan": "Last Quarter",
			"time_interval": "Weekly",
			"based_on": "date",
			"value_based_on": "profit_loss",
			"filters_json": json.dumps([["Daily Resource Report", "docstatus", "=", 1]]),
			"dynamic_filters_json": "",
			"is_public": 1,
			"is_standard": 1,
			"module": "Monitoring and Evaluation",
			"color": "#28a745",
		},
	]
	for chart in charts:
		_upsert_dashboard_chart(chart)
	frappe.db.commit()


def create_custom_blocks():
	blocks = [
		{
			"name": "Construction Home Guide",
			"html": _home_guide_html(),
			"style": _quick_stats_style(".cm-home-guide", "#171717", "#383838"),
		},
		{
			"name": "Bid Process Flow",
			"html": _workflow_html(
				"Bid Lifecycle",
				"fa-file-text",
				"#0289f7",
				[
					("1. Opportunity", "Bid Followup", "Track tenders, client, and purchase status."),
					("2. Assessment", "Site Visit Assessment → Detailed bid review", "Qualify the opportunity."),
					("3. Documentation", "Bid Documentation Checklist", "Prepare submission package."),
					("4. Opening", "Bid Opening Technical / Financial", "Record opening results."),
					("5. Follow-up", "Bid Opening Followup → Bid Result", "Capture outcomes."),
					("6. Estimating", "Cost Break Down", "Build priced BOQ for award decision."),
				],
			),
			"style": _workflow_style(),
		},
		{
			"name": "Contract Process Flow",
			"html": _workflow_html(
				"Contract Administration Flow",
				"fa-briefcase",
				"#e86c13",
				[
					("1. BOQ", "BOQ", "Define scope, quantities, and rates per project."),
					("2. Agreement", "Subcontract Agreement", "Link BOQ to subcontract terms."),
					("3. Measurement", "Takeoff", "Record executed quantities on site."),
					("4. Payment", "Subcontract Payment Certificate", "Certify work and process payment."),
					("5. Follow-up", "Weekly Contractual Followup", "Track progress, bonds, and time."),
					("6. Claims", "Claim Event Detail / Time Extension / Price Escalation", "Manage variations and delays."),
				],
			),
			"style": _workflow_style(),
		},
		{
			"name": "Monitoring Process Flow",
			"html": _workflow_html(
				"Monitoring & Evaluation Flow",
				"fa-chart-line",
				"#30a66d",
				[
					("1. Plan", "Weekly Action Plan", "Plan manpower, materials, equipment, and revenue."),
					("2. Execute", "Project tasks & site activities", "Work proceeds per weekly plan."),
					("3. Capture", "Daily Resource Report", "Pull labor, material, equipment, and revenue actuals."),
					("4. Compare", "WAP Daily Summary on plan", "Plan vs actual variance by day."),
					("5. Equipment", "Equipment Expense Report", "Fuel, hours, and equipment cost detail."),
					("6. Revenue", "Timesheet → DRR Revenue", "Billable hours linked to weekly plan."),
				],
			),
			"style": _workflow_style(),
		},
	]

	for block in blocks:
		if frappe.db.exists("Custom HTML Block", block["name"]):
			frappe.delete_doc("Custom HTML Block", block["name"], force=1)
		doc = frappe.get_doc(
			{
				"doctype": "Custom HTML Block",
				"name": block["name"],
				"html": block["html"],
				"style": block.get("style", ""),
				"private": 0,
			}
		)
		doc.insert(ignore_permissions=True)
	frappe.db.commit()


def create_dashboards():
	dashboards = [
		{
			"dashboard_name": "Construction Management",
			"module": "Construction Management",
			"cards": [
				{"card": "Construction Projects"},
				{"card": "Purchased Bids"},
				{"card": "Active Subcontract Agreements"},
				{"card": "Daily Report Profit"},
			],
			"charts": [{"chart": "Construction Project Trend", "width": "Full"}],
		},
		{
			"dashboard_name": "Bid",
			"module": "Bid",
			"cards": [
				{"card": "Purchased Bids"},
				{"card": "Open Bid Followups"},
				{"card": "Submitted Cost Breakdowns"},
			],
			"charts": [{"chart": "Bid Followup Trend", "width": "Full"}],
		},
		{
			"dashboard_name": "Contract Administration",
			"module": "Contract Administration",
			"cards": [
				{"card": "Active Subcontract Agreements"},
				{"card": "Submitted BOQs"},
				{"card": "Payment Certificates"},
			],
			"charts": [{"chart": "Agreement Value by Project", "width": "Full"}],
		},
		{
			"dashboard_name": "Monitoring and Evaluation",
			"module": "Monitoring and Evaluation",
			"cards": [
				{"card": "Weekly Action Plans"},
				{"card": "Daily Resource Reports"},
				{"card": "Daily Report Profit"},
				{"card": "Daily Report Cost"},
			],
			"charts": [
				{"chart": "Daily Resource Reports Trend", "width": "Half"},
				{"chart": "Profit vs Cost Trend", "width": "Half"},
			],
		},
	]

	for data in dashboards:
		name = data["dashboard_name"]
		if frappe.db.exists("Dashboard", name):
			doc = frappe.get_doc("Dashboard", name)
		else:
			doc = frappe.new_doc("Dashboard")
			doc.dashboard_name = name

		doc.cards = []
		for row in data.get("cards", []):
			doc.append("cards", row)
		doc.charts = []
		for row in data.get("charts", []):
			doc.append("charts", row)
		doc.module = data["module"]
		doc.is_standard = 1
		if doc.is_new():
			doc.insert(ignore_permissions=True)
		else:
			doc.save(ignore_permissions=True)

	frappe.db.commit()


def sync_workspaces():
	from construction_management.workspace_builder import sync_all_workspaces

	sync_all_workspaces()


def export_workspaces():
	if not frappe.conf.developer_mode:
		return

	for name in (
		"Construction Management",
		"Bid",
		"Contract Administration",
		"Monitoring and Evaluation",
	):
		frappe.modules.export_doc("Workspace", name)


def _upsert_number_card(card):
	name = card["name"]
	if frappe.db.exists("Number Card", name):
		doc = frappe.get_doc("Number Card", name)
		for key, value in card.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc({"doctype": "Number Card", **card})
	doc.name = name
	doc.insert(ignore_permissions=True)


def _upsert_dashboard_chart(chart):
	name = chart["chart_name"]
	if frappe.db.exists("Dashboard Chart", name):
		# Standard charts cannot be updated on production sites (non-developer mode).
		if not frappe.conf.developer_mode:
			return
		doc = frappe.get_doc("Dashboard Chart", name)
		for key, value in chart.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
		return

	frappe.get_doc({"doctype": "Dashboard Chart", **chart}).insert(ignore_permissions=True)


def _home_guide_html():
	return """
		<div class="cm-home-guide">
			<div class="stats-icon"><i class="fa fa-hard-hat"></i></div>
			<div class="stats-content">
				<h5>Construction Management Hub</h5>
				<p>End-to-end flow: <strong>Bid</strong> → win work → <strong>Contract Administration</strong> →
				<strong>Monitoring &amp; Evaluation</strong> on every active project.</p>
			</div>
		</div>
	"""


def _workflow_html(title, icon, color, steps):
	parts = []
	for idx, (title_step, doctype, desc) in enumerate(steps, 1):
		parts.append(
			f"""
		<div class="flow-step">
			<div class="flow-num" style="background:{color}">{idx}</div>
			<div class="flow-body">
				<strong>{title_step}</strong>
				<span class="flow-doctype">{doctype}</span>
				<p>{desc}</p>
			</div>
		</div>
		"""
		)
		if idx < len(steps):
			parts.append(
				'<span class="flow-arrow" aria-hidden="true"><i class="fa fa-chevron-right"></i></span>'
			)
	steps_html = "".join(parts)
	return f"""
		<div class="cm-workflow-block">
			<div class="flow-header" style="background:linear-gradient(135deg, {color} 0%, {color}dd 100%)">
				<i class="fa {icon}"></i>
				<h5>{title}</h5>
			</div>
			<div class="flow-steps">{steps_html}</div>
		</div>
	"""


def _workflow_style():
	return """
		.cm-workflow-block {
			border-radius: 8px;
			overflow: hidden;
			box-shadow: 0 2px 6px rgba(0,0,0,0.1);
			background: #fff;
		}
		.cm-workflow-block .flow-header {
			padding: 10px 16px;
			display: flex;
			align-items: center;
			gap: 10px;
			color: #fff;
		}
		.cm-workflow-block .flow-header h5 { margin: 0; font-weight: 600; color: #fff; font-size: 14px; }
		.cm-workflow-block .flow-header i { font-size: 16px; }
		.cm-workflow-block .flow-steps {
			display: flex;
			flex-direction: row;
			align-items: stretch;
			flex-wrap: nowrap;
			overflow-x: auto;
			padding: 10px 12px;
			gap: 0;
			scrollbar-width: thin;
		}
		.cm-workflow-block .flow-step {
			display: flex;
			flex-direction: column;
			align-items: center;
			text-align: center;
			flex: 1 1 0;
			min-width: 120px;
			max-width: 200px;
			padding: 6px 8px;
		}
		.cm-workflow-block .flow-arrow {
			display: flex;
			align-items: center;
			flex-shrink: 0;
			color: #c4c4c4;
			padding: 0 2px;
			font-size: 11px;
		}
		.cm-workflow-block .flow-num {
			width: 24px;
			height: 24px;
			border-radius: 50%;
			color: #fff;
			font-size: 11px;
			font-weight: 700;
			display: flex;
			align-items: center;
			justify-content: center;
			flex-shrink: 0;
			margin-bottom: 6px;
		}
		.cm-workflow-block .flow-body strong {
			display: block;
			font-size: 11px;
			color: #171717;
			line-height: 1.25;
			margin-bottom: 2px;
		}
		.cm-workflow-block .flow-doctype {
			display: block;
			font-size: 10px;
			color: #2490ef;
			margin-bottom: 3px;
			line-height: 1.2;
		}
		.cm-workflow-block .flow-body p {
			margin: 0;
			font-size: 10px;
			color: #6c757d;
			line-height: 1.3;
			display: -webkit-box;
			-webkit-line-clamp: 2;
			-webkit-box-orient: vertical;
			overflow: hidden;
		}
		@media (max-width: 992px) {
			.cm-workflow-block .flow-steps { flex-wrap: wrap; }
			.cm-workflow-block .flow-arrow { display: none; }
			.cm-workflow-block .flow-step { min-width: 45%; max-width: none; }
		}
	"""


def _quick_stats_style(selector, c1, c2):
	return f"""
		{selector} {{
			border-radius: 8px;
			background: linear-gradient(135deg, {c1} 0%, {c2} 100%);
			padding: 24px;
			display: flex;
			align-items: center;
			gap: 20px;
			box-shadow: 0 2px 8px rgba(0,0,0,0.15);
		}}
		{selector} .stats-icon {{
			width: 56px;
			height: 56px;
			border-radius: 12px;
			background: rgba(255,255,255,0.15);
			display: flex;
			align-items: center;
			justify-content: center;
		}}
		{selector} .stats-icon i {{ font-size: 28px; color: #fff; }}
		{selector} .stats-content h5 {{ color: #fff; font-weight: 600; margin: 0 0 6px; }}
		{selector} .stats-content p {{ color: rgba(255,255,255,0.9); margin: 0; font-size: 14px; }}
	"""
