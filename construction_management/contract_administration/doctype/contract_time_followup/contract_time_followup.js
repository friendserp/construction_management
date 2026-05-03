frappe.ui.form.on("Contract Time Followup", {
	refresh(frm) {

	},
});

frappe.ui.form.on("Contract Time Detail", {
	commencement_date(frm, cdt, cdn) {
		calculate_dates(frm, cdt, cdn);
	},
	original_duration(frm, cdt, cdn) {
		calculate_dates(frm, cdt, cdn);
	},
	approved_eot(frm, cdt, cdn) {
		calculate_dates(frm, cdt, cdn);
	},
	project(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.project) {
			// Fetch project details if needed, for now we assume manual entry or custom fetch
		}
	}
});

function calculate_dates(frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);
	
	// Original Completion Date
	if (row.commencement_date && row.original_duration) {
		let original_completion = frappe.datetime.add_days(row.commencement_date, row.original_duration);
		frappe.model.set_value(cdt, cdn, "original_completion_date", original_completion);
		
		// Revised Completion Date (if EOT exists)
		if (row.approved_eot) {
			let revised_completion = frappe.datetime.add_days(original_completion, row.approved_eot);
			frappe.model.set_value(cdt, cdn, "revised_completion_date", revised_completion);
		} else {
			frappe.model.set_value(cdt, cdn, "revised_completion_date", original_completion);
		}
	}
}
