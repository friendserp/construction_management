// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bid Opening Followup", {
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

                    return frappe.db.get_value('Bid Followup', bid_followup_id,
                        ['client', 'date_of_announcement', 'opening_time', 'opening_place', 'project_place']
                    );
                }
            })
            .then(r => {
                console.log("Bid Followup data:", r)
                if (r && r.message) {
                    if (r.message.client) {
                        frm.set_value("name_of_client", r.message.client)
                    }
                    if (r.message.date_of_announcement) {
                        frm.set_value("announcement_date", r.message.date_of_announcement)
                    }
                    if (r.message.opening_time) {
                        frm.set_value("opening_date", r.message.opening_time)
                    }
                    if (r.message.opening_place) {
                        frm.set_value("opening_place", r.message.opening_place)
                    }
                    if (r.message.project_place) {
                        frm.set_value("project_name", r.message.project_place)
                    }
                }
            })
            .catch(err => {
                console.error("Error fetching data:", err)
                frappe.msgprint(__("Error fetching data from Bid Documentation Checklist or Bid Followup"))
            })
    },
    refresh: function (frm) {
        frm.add_custom_button(__("Create Bid Result"), function () {
            frappe.new_doc("Bid Result", {
                bid_opening_followup_id: frm.doc.name
            });
        }, __("Create"));

        frm.add_custom_button(__("Create Unqualified Bid Purchased"), function () {
            frappe.new_doc("Unqualified Bid Purchased", {
                bid_opening_followup_id: frm.doc.name
            });
        }, __("Create"));

        frm.add_custom_button(__("Create None Responsive Bid"), function () {
            frappe.new_doc("None Responsive Bid", {
                bid_opening_followup_id: frm.doc.name
            });
        }, __("Create"));
    }
});