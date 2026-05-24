# Copyright (c) 2026, Friends ERP and contributors

import frappe
from frappe import _


def execute():
	"""Pre-install checks (does not block install)."""
	installed = frappe.get_installed_apps() or []

	if "erpnext" not in installed:
		frappe.throw(
			_(
				"ERPNext must be installed before Construction Management. "
				"Run: bench --site {0} install-app erpnext"
			).format(frappe.local.site)
		)

	if "klc_custom" not in installed:
		frappe.msgprint(
			_(
				"Note: <b>klc_custom</b> is not installed. Some features need it "
				"(Daily Cost Report, Equipment Master, extended Timesheet fields). "
				"Install klc_custom from your bench apps folder before using M&amp;E daily costing."
			),
			title=_("Optional dependency"),
			indicator="orange",
		)
