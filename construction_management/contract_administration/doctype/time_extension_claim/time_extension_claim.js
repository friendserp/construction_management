frappe.ui.form.on("Time Extension Claim", {
	project(frm) {
		if (frm.doc.project) {
			frappe.db.get_value("Project", frm.doc.project, ["customer", "consultant"], (r) => {
				if (r) {
					frm.set_value("employer", r.customer);
					frm.set_value("consultant", r.consultant);
				}
			});
		}
	}
});
