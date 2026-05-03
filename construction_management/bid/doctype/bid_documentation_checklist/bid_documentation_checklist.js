// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bid Documentation Checklist', {
    template: function (frm) {
        if (frm.doc.template) {
            fetch_bid_template_items(frm, frm.doc.template);
        }
    },

    bid_followup_id: function (frm) {
        frm.set_query('site_visit_assessment_id', function () {
            if (frm.doc.bid_followup_id) {
                return {
                    filters: {
                        bid_followup_id: frm.doc.bid_followup_id
                    }
                };
            }
            return {
                filters: {}
            };
        });
    },

    site_visit_assessment_id: function (frm) {
        if (frm.doc.site_visit_assessment_id) {
            frappe.db.get_value('Site Visit Assessment', frm.doc.site_visit_assessment_id, 'bid_followup_id')
                .then(r => {
                    if (r && r.message && r.message.bid_followup_id) {
                        if (!frm.doc.bid_followup_id) {
                            frm.set_value('bid_followup_id', r.message.bid_followup_id);
                        } else if (r.message.bid_followup_id !== frm.doc.bid_followup_id) {
                            frappe.msgprint(__("This Site Visit Assessment is not linked to the selected Bid Followup. Please select a valid assessment."));
                            frm.set_value('site_visit_assessment_id', '');
                        }
                    }
                });
        }
    },

    refresh: function (frm) {

        let status_value = frm.doc.status;

        console.log({ status_value })
        let status_html_content = `<span style="background-color: #28a745; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 500; font-size: 12px;"> ${status_value}</span>`;

        let form_header = $('.form-page .form-header');
        if (form_header.length) {
            // form_header.find('.custom-status-indicator').remove();

            form_header.append(`
                <div class="custom-status-indicator" style="display: inline-flex; align-items: center; margin-left: 15px; gap: 8px;">
                    <label style="margin: 0; font-weight: 500; color: #6c757d;">Status:</label>
                    ${status_html_content}
                </div>
            `);
        }
    }

});

function fetch_bid_template_items(frm, template_name) {
    frm.clear_table('items');
    frappe.db.get_doc('Bid Template', template_name)
        .then(doc => {
            if (doc.items && doc.items.length > 0) {
                doc.items.forEach(item => {
                    let child = frm.add_child('items');
                    child.description = item.description;
                });

                frm.refresh_field('items');

            } else {
                frappe.msgprint(__('No checklist items found in the selected Bid Template'));
                frm.refresh_field('items');
            }
        })
        .catch(err => {
            frappe.msgprint(__('Error fetching Bid Template: {0}', [err.message]));
            frm.clear_table('items');
            frm.refresh_field('items');
        });
}