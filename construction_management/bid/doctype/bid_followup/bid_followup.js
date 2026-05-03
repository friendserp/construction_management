// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bid Followup', {
    refresh: function(frm) {
        let status_value = frm.doc.status;
        let status_html_content = '';
        
        console.log("status value", status_value);
        if (status_value === "Purchased") {
            status_html_content = '<span style="background-color: #28a745; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 500; font-size: 12px;">✓ Purchased</span>';
        } else if (status_value === "Skipped") {
            status_html_content = '<span style="background-color: #ffc107; color: #856404; padding: 4px 12px; border-radius: 4px; font-weight: 500; font-size: 12px;">⏭ Skipped</span>';
        } else if (status_value === "Overdue") {
            status_html_content = '<span style="background-color: #dc3545; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 500; font-size: 12px;">⚠ Overdue</span>';
        } else {
            status_html_content = `<span style="background-color: #6c757d; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 500; font-size: 12px;">${status_value || 'Unknown'}</span>`;
        }
        
        let form_header = $('.form-page .form-header');
        if (form_header.length) {
            form_header.find('.custom-status-indicator').remove();
            
            form_header.append(`
                <div class="custom-status-indicator" style="display: inline-flex; align-items: center; margin-left: 15px; gap: 8px;">
                    <label style="margin: 0; font-weight: 500; color: #6c757d;">Status:</label>
                    ${status_html_content}
                </div>
            `);
        }

        // Add Update Status button with better UI
        frm.add_custom_button(__("Update Status"), function() {
            let dialog = new frappe.ui.Dialog({
                title: __("Update Status"),
                fields: [
                    {
                        fieldname: "status",
                        fieldtype: "Select",
                        label: __("Select Status"),
                        options: [
                            {value: "Purchased", label: "✓ Purchased"},
                            {value: "Skipped", label: "⏭ Skipped"},
                            {value: "Overdue", label: "⚠ Overdue"}
                        ],
                        reqd: 1,
                        default: frm.doc.status
                    },
                    {
                        fieldname: "remark",
                        fieldtype: "Small Text",
                        label: __("Remark (Optional)"),
                        placeholder: __("Add any remark about this status update...")
                    }
                ],
                primary_action_label: __("Update Status"),
                primary_action: function(values) {
                    let status_value = values.status;
                    let remark = values.remark;
                    
                    if (!status_value) {
                        frappe.msgprint(__("Please select a status"));
                        return;
                    }
                    
                    console.log("Updating status to:", status_value);
                    frm.set_value("status", status_value);
                    
                    if (remark) {
                        frm.set_value("remark", remark);
                    }
                    
                    frm.save();
                    dialog.hide();
                    
                    // Show success message
                    frappe.show_alert({
                        message: __("Status updated to {0}", [status_value]),
                        indicator: "green"
                    }, 3);
                    
                    // Refresh the form to update the status display
                    frm.refresh();
                }
            });
            dialog.show();
        }).addClass("btn-primary");
        
        // Add icon to the Update Status button
        setTimeout(function() {
            $(".btn-primary").filter(function() {
                return $(this).text().includes("Update Status");
            }).prepend('<i class="fa fa-edit" style="margin-right: 5px;"></i> ');
        }, 100);

        // If status is purchased then add a button that redirects to the site visit assessment page
        if (frm.doc.status === "Purchased") {
            frm.add_custom_button(__("Create Site Visit Assessment"), function() {
                // Create a new Site Visit Assessment document with reference to this Bid Followup
                frappe.new_doc("Site Visit Assessment", {
                    "bid_followup_id": frm.doc.name
                });
            }).addClass("btn-primary");
            
            // Add icon to the button
            setTimeout(function() {
                $(".btn-primary").filter(function() {
                    return $(this).text().includes("Create Site Visit Assessment");
                }).prepend('<i class="fa fa-plus" style="margin-right: 5px;"></i> ');
            }, 100);
        }
    }
});