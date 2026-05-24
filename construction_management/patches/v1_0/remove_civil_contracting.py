# Copyright (c) 2026, Friends ERP and contributors
"""Remove legacy Civil Contracting doctypes from the database."""

import frappe

CIVIL_DOCTYPES = (
	# Child tables first
	"Worker Sheet Attendance",
	"Worker Sheet Settings Wages",
	"Worker Sheet Settings Outstanding",
	"Worker Sheet Settings Other",
	"Wage Slip Allocation",
	"Measurement Sheet Item",
	"Measurement Book Record",
	"Running Account Bill Items",
	"Running Account Bill Invoices",
	"Worker Sheet Settings",
	# Parents
	"Worker Sheet",
	"Wage Slip",
	"Measurement Sheet",
	"Measurement Book",
	"Running Account Bill",
	"Worker",
)


def execute():
	"""Drop Civil Contracting DocTypes from the site (files removed from app)."""
	frappe.flags.ignore_links = True

	for doctype in CIVIL_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		try:
			frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)
		except Exception:
			frappe.log_error(title=f"Remove civil doctype: {doctype}")

	if frappe.db.exists("Module Def", "Civil Contracting"):
		try:
			frappe.delete_doc("Module Def", "Civil Contracting", force=True, ignore_missing=True)
		except Exception:
			pass

	frappe.db.commit()
	frappe.clear_cache()
