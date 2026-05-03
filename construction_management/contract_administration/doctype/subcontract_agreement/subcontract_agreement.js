// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Subcontract Agreement", {
    advance_percent(frm) {
        if (frm.doc.advance_percent) {
            frm.set_value("advance_amount", frm.doc.total_price_with_vat * frm.doc.advance_percent / 100);
            frm.refresh_field("advance_amount");
        }
    }
});

frappe.ui.form.on("Subcontract Agreement Items", {
    qty(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
});

function calculate_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.qty && row.rate) {
        frappe.model.set_value(cdt, cdn, "amount", row.qty * row.rate);

        let total_amount = 0;
        for (let i = 0; i < frm.doc.items.length; i++) {
            total_amount += frm.doc.items[i].amount;
        }

        let vat_amount = total_amount * 0.15;
        let total_amount_with_vat = total_amount + vat_amount;
        frm.set_value("total_price_before_vat", total_amount);
        frm.set_value("vat", vat_amount);
        frm.set_value("total_price_with_vat", total_amount_with_vat);
        frm.refresh_field("items");

    }
}