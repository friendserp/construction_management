frappe.ui.form.on("Delay Justification", {
	onload(frm) {
		if (frm.is_new()) {
			frm.set_value("prepared_by", frappe.session.user);
			frm.set_value("date", frappe.datetime.get_today());
		}
	}
});
