# Copyright (c) 2026, Friends ERP and contributors

import frappe
from frappe import _
from frappe.model.document import Document


class BidFollowup(Document):
	pass


@frappe.whitelist()
def create_project_from_bid_followup(bid_followup):
	"""Create an ERPNext Project from a purchased bid followup."""
	bf = frappe.get_doc("Bid Followup", bid_followup)

	if bf.project:
		frappe.throw(_("Project {0} is already linked to this bid followup.").format(bf.project))

	if not bf.project_name:
		frappe.throw(_("Tender / Project Name is required before creating a project."))

	project = frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": bf.project_name,
			"customer": bf.client,
		}
	)
	if bf.project_type and frappe.get_meta("Project").has_field("project_type"):
		project.project_type = bf.project_type

	project.insert(ignore_permissions=True)

	frappe.db.set_value("Bid Followup", bf.name, "project", project.name, update_modified=True)

	return {"project": project.name}
