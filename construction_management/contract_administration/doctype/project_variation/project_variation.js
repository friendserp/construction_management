frappe.ui.form.on("Project Variation", {
	project(frm) {
		if (frm.doc.project) {
			frappe.db.get_value("Project", frm.doc.project, ["customer", "consultant"], (r) => {
				if (r) {
					frm.set_value("client", r.customer);
					frm.set_value("consultant", r.consultant);
				}
			});
		}
	},
	contract_amount(frm) {
		calculate_all_percentages(frm);
	}
});

frappe.ui.form.on("Project Variation Item", {
	amount(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (frm.doc.contract_amount) {
			let percentage = (row.amount / frm.doc.contract_amount) * 100;
			frappe.model.set_value(cdt, cdn, "percentage", percentage);
		}
		calculate_total_amount(frm);
	},
	variations_remove(frm) {
		calculate_total_amount(frm);
	}
});

function calculate_all_percentages(frm) {
	if (frm.doc.contract_amount) {
		frm.doc.variations.forEach(row => {
			let percentage = (row.amount / frm.doc.contract_amount) * 100;
			frappe.model.set_value(row.doctype, row.name, "percentage", percentage);
		});
	}
}

function calculate_total_amount(frm) {
	let total = 0;
	frm.doc.variations.forEach(row => {
		total += row.amount || 0;
	});
	frm.set_value("total_variation_amount", total);
}
