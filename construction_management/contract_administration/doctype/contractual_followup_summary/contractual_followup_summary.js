frappe.ui.form.on("Contractual Followup Summary", {
	refresh(frm) {

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
