// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bid Opening Financial", {
    refresh(frm) {

    },
    bid_documentation_check_list: function (frm) {
        console.log("bid_documentation_check_list", frm.doc.bid_documentation_check_list)

        if (!frm.doc.bid_documentation_check_list) {
            return;
        }

        frappe.db.get_value('Bid Documentation Checklist', frm.doc.bid_documentation_check_list, 'bid_followup_id')
            .then(r => {
                console.log("Bid Documentation Checklist data:", r)
                if (r && r.message && r.message.bid_followup_id) {
                    let bid_followup_id = r.message.bid_followup_id;

                    return frappe.db.get_value('Detailed bid review', bid_followup_id,
                        ['client', 'bid_opening_time', 'place_of_bid_submission', 'project_name']
                    );
                }
            })
            .then(r => {
                console.log("Bid Followup data:", r)
                if (r && r.message) {
                    if (r.message.client) {
                        frm.set_value("name_of_client", r.message.client)
                    }
                    if (r.message.bid_opening_time) {
                        frm.set_value("opening_date", r.message.bid_opening_time)
                    }
                    if (r.message.place_of_bid_submission) {
                        frm.set_value("opening_place", r.message.place_of_bid_submission)
                    }
                    if (r.message.project_name) {
                        frm.set_value("project_name", r.message.project_name)
                    }
                }
            })
            .catch(err => {
                console.error("Error fetching data:", err)
                frappe.msgprint(__("Error fetching data from Bid Documentation Checklist or Bid Followup"))
            })
    },
});
