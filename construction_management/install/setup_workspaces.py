# Copyright (c) 2026, Friends ERP and contributors

import frappe


def execute():
	"""Setup workspaces, charts, number cards, and custom blocks."""
	from construction_management.dashboard_fixtures import setup_all

	setup_all()
	print("Construction Management workspaces and dashboards are ready.")
