// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Daily Resource Report', {
	setup: function(frm) {
		// Set project-based query filters if needed
	},
	project: function(frm) {
		fetch_totals(frm);
	},
	date: function(frm) {
		fetch_totals(frm);
	}
});

function fetch_totals(frm) {
	if (frm.doc.project && frm.doc.date) {
		frm.call({
			method: 'fetch_totals',
			doc: frm.doc,
			callback: function(r) {
				if (r.message) {
					$.each(r.message, function(fieldname, value) {
						frm.set_value(fieldname, value);
					});
				}
			}
		});
	}
}
