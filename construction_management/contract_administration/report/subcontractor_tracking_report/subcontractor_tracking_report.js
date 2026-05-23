// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.query_reports["Subcontractor Tracking Report"] = {
	"filters": [
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project"
		}
	]
};
