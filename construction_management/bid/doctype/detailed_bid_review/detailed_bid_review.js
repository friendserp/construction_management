// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Detailed bid review', {
	refresh(frm) {
        if(frm.doc.site_visit){
            //add a button that says create site visit assessment in Actions tab
            frm.add_custom_button(__("Create Site Visit Assessment"), function () {
                frappe.new_doc("Site Visit Assessment", {
                    detailed_bid_review_id: frm.doc.name,
                    bid_followup_id: frm.doc.bid_followup_id,
                });
            }, __("Actions"));
        }

	},
});

