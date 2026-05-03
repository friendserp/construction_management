frappe.ui.form.on("Claim Event Detail", {
	weekly_followup(frm) {
		if (frm.doc.weekly_followup) {
			frappe.db.get_doc("Weekly Contractual Followup", frm.doc.weekly_followup).then(doc => {
				frm.set_value({
					"project": doc.project,
					"project_location": doc.project_location,
					"client": doc.client,
					"consultant": doc.consultant,
					"contractor": doc.contractor,
					"from_date": doc.from_date,
					"to_date": doc.to_date
				});

				if (frm.doc.claim_details.length === 0 && doc.from_date) {
					const days = [
						{ field: "monday", offset: 0 },
						{ field: "tuesday", offset: 1 },
						{ field: "wednesday", offset: 2 },
						{ field: "thursday", offset: 3 },
						{ field: "firday", offset: 4 },
						{ field: "saturday", offset: 5 },
						{ field: "sunday", offset: 6 }
					];

					doc.claim_issues.forEach(issue_row => {
						days.forEach(day => {
							if (issue_row[day.field] === 1) {
								let child = frm.add_child("claim_details");
								child.date = frappe.datetime.add_days(doc.from_date, day.offset);
								child.issue = issue_row.issue; // Set the whole issue text
							}
						});
					});
					frm.refresh_field("claim_details");
				}
			});
		}
	}
});
