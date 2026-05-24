# Copyright (c) 2026, Friends ERP and contributors

import frappe


def execute():
	"""Ensure dashboards, workspaces, and Projects User permissions exist after upgrade."""
	from construction_management.dashboard_fixtures import setup_all

	setup_all()
