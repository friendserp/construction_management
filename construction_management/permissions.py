# Copyright (c) 2026, Friends ERP and contributors

import frappe

# ERPNext standard role (user-facing name is often "Project User")
PROJECTS_USER_ROLE = "Projects User"
PROJECTS_MANAGER_ROLE = "Projects Manager"
SYSTEM_MANAGER_ROLE = "System Manager"

WORKSPACE_ACCESS_ROLES = [
	PROJECTS_USER_ROLE,
	PROJECTS_MANAGER_ROLE,
	SYSTEM_MANAGER_ROLE,
]

APP_MODULES = [
	"Construction Management",
	"Bid",
	"Contract Administration",
	"Monitoring and Evaluation",
]

_BASE_PERMS = {
	"read": 1,
	"write": 1,
	"create": 1,
	"delete": 1,
	"email": 1,
	"export": 1,
	"print": 1,
	"report": 1,
	"share": 1,
}

_SUBMIT_PERMS = {
	"submit": 1,
	"cancel": 1,
	"amend": 1,
}


def setup_all():
	"""Grant Projects User access to all app doctypes and desk assets."""
	setup_doctype_permissions()
	setup_desk_asset_permissions()
	frappe.db.commit()
	frappe.clear_cache()


def setup_doctype_permissions():
	"""Add Projects User / Projects Manager permissions on every app DocType."""
	doctypes = frappe.get_all(
		"DocType",
		filters={"module": ["in", APP_MODULES], "istable": 0},
		pluck="name",
	)

	for doctype in doctypes:
		meta = frappe.get_meta(doctype)
		for role in (PROJECTS_USER_ROLE, PROJECTS_MANAGER_ROLE):
			if _has_role_perm(doctype, role):
				continue
			perms = dict(_BASE_PERMS)
			if meta.is_submittable:
				perms.update(_SUBMIT_PERMS)
			_add_docperm(doctype, role, perms)

	# Child tables: read/write so grid rows work when parent is editable
	child_doctypes = frappe.get_all(
		"DocType",
		filters={"module": ["in", APP_MODULES], "istable": 1},
		pluck="name",
	)
	for doctype in child_doctypes:
		for role in (PROJECTS_USER_ROLE, PROJECTS_MANAGER_ROLE):
			if _has_role_perm(doctype, role):
				continue
			_add_docperm(
				doctype,
				role,
				{"read": 1, "write": 1, "create": 1, "delete": 1},
			)


def setup_desk_asset_permissions():
	"""Ensure workspace widgets (cards, charts, blocks) are readable."""
	for role in (PROJECTS_USER_ROLE, PROJECTS_MANAGER_ROLE):
		for doctype in (
			"Number Card",
			"Dashboard Chart",
			"Dashboard",
			"Custom HTML Block",
			"Workspace",
		):
			_add_role_if_missing(doctype, role, read=1)


def workspace_roles():
	"""Roles allowed to see Construction Management workspaces."""
	return [{"role": role} for role in WORKSPACE_ACCESS_ROLES]


def _has_role_perm(doctype, role):
	return frappe.db.exists(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
	)


def _add_docperm(doctype, role, perms):
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

	frappe.permissions.setup_custom_perms(doctype)

	existing = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Custom DocPerm", existing)
		for key, value in perms.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
				**perms,
			}
		)
		doc.insert(ignore_permissions=True)

	validate_permissions_for_doctype(doctype)


def _add_role_if_missing(doctype, role, **perms):
	if _has_role_perm(doctype, role):
		existing = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			"name",
		)
		doc = frappe.get_doc("Custom DocPerm", existing)
		for key, value in perms.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
		return

	try:
		_add_docperm(doctype, role, perms)
	except Exception as exc:
		frappe.log_error(
			title=f"Desk permission setup failed: {doctype} / {role}",
			message=frappe.get_traceback(),
		)
		frappe.logger("construction_management").warning(
			"Could not add %s on %s: %s", role, doctype, exc
		)
