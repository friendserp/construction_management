frappe.ui.form.on("Performance Bond Followup", {
	refresh(frm) {

	},
});

frappe.ui.form.on("Performance Bond Detail", {
	expiry_date(frm, cdt, cdn) {
		calculate_remaining_days(frm, cdt, cdn);
	},
	issue_date(frm, cdt, cdn) {
		calculate_remaining_days(frm, cdt, cdn);
	}
});

function calculate_remaining_days(frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);
	if (row.expiry_date) {
		let today = frappe.datetime.get_today();
		let diff = frappe.datetime.get_diff(row.expiry_date, today);
		frappe.model.set_value(cdt, cdn, "remaining_days", diff);
	}
}
