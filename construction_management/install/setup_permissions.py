# Copyright (c) 2026, Friends ERP and contributors

import frappe


def execute():
	from construction_management.permissions import setup_all

	setup_all()
	print("Projects User permissions applied for Construction Management app.")
