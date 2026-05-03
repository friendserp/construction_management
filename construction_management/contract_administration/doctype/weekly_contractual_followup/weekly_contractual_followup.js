frappe.ui.form.on("Weekly Contractual Followup", {
	refresh(frm) {
		if (frm.doc.claim_issues.length === 0) {
			const issues = [
				{ issue: "1.1 Missed drawing" },
				{ issue: "1.2 Design discrepancies" },
				{ issue: "1.3 Design modification at site level" },
				{ issue: "2.1 Works indicated on drawing and missed in BOQ or vice versa" },
				{ issue: "2.2 Additional work order given" },
				{ issue: "2.3 Change in work item (quality, or shape /dimension or quantity from BOQ)" },
				{ issue: "3.1 Bad Weather conditions and natural hazards" },
				{ issue: "3.2 Delay due to inspection / approval" },
				{ issue: "3.3 Force majeure issues" },
				{ issue: "3.4 Artificial conditions or Physical obstructions" },
				{ issue: "3.5 Other external factors" }
			];

			issues.forEach(row => {
				let child = frm.add_child("claim_issues");
				child.issue = row.issue;
			});

			frm.refresh_field("claim_issues");
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__("Create Detailed Event"), () => {
				frappe.new_doc("Claim Event Detail", {
					weekly_followup: frm.doc.name,
					project: frm.doc.project,
					project_location: frm.doc.project_location,
					client: frm.doc.client,
					consultant: frm.doc.consultant,
					contractor: frm.doc.contractor
				});
			});
		}
	},
	from_date(frm) {
		if (frm.doc.from_date) {
			frm.set_value("to_date", frappe.datetime.add_days(frm.doc.from_date, 6));
		}
	},
	project(frm) {
		if (frm.doc.project) {
			frappe.db.get_value("Project", frm.doc.project, ["customer", "consultant"], (r) => {
				if (r) {
					frm.set_value("client", r.customer);
					frm.set_value("consultant", r.consultant);
				}
			});
		}
	}
});
