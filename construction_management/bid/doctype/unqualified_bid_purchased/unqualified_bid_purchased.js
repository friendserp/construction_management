// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Unqualified Bid Purchased', {
    refresh: function (frm) {
        if (!frm.is_new()) {
            generate_flow_chart(frm);
        }
    },

    bid_opening_followup_id: function (frm) {
        if (frm.doc.bid_opening_followup_id) {
            generate_flow_chart(frm);
        }
    }
});

function generate_flow_chart(frm) {
    frappe.call({
        method: "construction_management.bid.doctype.unqualified_bid_purchased.unqualified_bid_purchased.get_bid_flow",
        args: {
            doctype: frm.doc.doctype,
            docname: frm.doc.name
        },
        callback: function (r) {
            if (r.message) {
                render_flow_chart(frm, r.message);
            }
        }
    });
}

function render_flow_chart(frm, flow_items) {
	let html = `
		<div class="flow-chart-container" style="margin: 20px 0; border: 1px solid #d1d8dd; border-radius: 8px; background: #fff;">
			<div style="padding: 10px 15px; border-bottom: 1px solid #d1d8dd; font-weight: bold; background: #f8f9fb;">Bid Process Flow</div>
			<div style="padding: 15px; display: flex; align-items: center; gap: 15px; overflow-x: auto;">
	`;

	flow_items.forEach((item, i) => {
		let is_current = item.current;
		html += `
			<div class="flow-step" style="display: flex; align-items: center; gap: 10px;">
				<div onclick="frappe.set_route('Form', '${item.doctype}', '${item.id}')" 
					 style="cursor: pointer; padding: 10px 15px; border: 1px solid ${is_current ? '#2196f3' : '#d1d8dd'}; 
							border-radius: 6px; background: ${is_current ? '#e3f2fd' : '#fcfcfc'}; white-space: nowrap; transition: all 0.2s;">
					<span style="font-size: 18px; margin-right: 8px;">${item.icon}</span>
					<span style="font-weight: 600; color: ${is_current ? '#0d47a1' : '#36414c'};">${item.label}</span>
					<div style="font-size: 11px; color: #8d99a6; margin-top: 4px;">${item.id}</div>
				</div>
				${i < flow_items.length - 1 ? '<span style="color: #d1d8dd; font-size: 20px;">→</span>' : ''}
			</div>
		`;
	});

	html += `</div></div>`;
	
	if (frm.fields_dict.flow_html) {
		frm.fields_dict.flow_html.$wrapper.html(html);
	}
}