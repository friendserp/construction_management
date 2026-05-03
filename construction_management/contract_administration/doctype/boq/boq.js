frappe.ui.form.on('BOQ', {
    validate(frm) {
        update_summary(frm);
        calculate_totals(frm);
    }
});

frappe.ui.form.on("BOQ Items", {
    qty(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    }
});

frappe.ui.form.on("BOQ Summary", {
    previous_amount(frm, cdt, cdn) {
        calculate_todate(frm, cdt, cdn);
    },
    current_amount(frm, cdt, cdn) {
        calculate_todate(frm, cdt, cdn);
    }
});

function calculate_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let qty = flt(row.qty);
    let rate = flt(row.rate);
    let c_qty = flt(row.c_qty);
    let p_qty = flt(row.p_qty);
    let t_qty = flt(row.t_qty);
    frappe.model.set_value(cdt, cdn, "amount", qty * rate);
    frappe.model.set_value(cdt, cdn, "c_amount", c_qty * rate);
    frappe.model.set_value(cdt, cdn, "p_amount", p_qty * rate);
    frappe.model.set_value(cdt, cdn, "t_amount", t_qty * rate);
    frm.refresh_field("items");
}

function calculate_todate(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let previous = flt(row.previous_amount);
    let current = flt(row.current_amount);
    frappe.model.set_value(cdt, cdn, "todate_amount", previous + current);
    calculate_totals(frm);
}

function calculate_totals(frm) {
    if (!frm.doc.summary) return;

    let total_previous = 0;
    let total_current = 0;
    let total_todate = 0;

    frm.doc.summary.forEach(row => {
        total_previous += flt(row.previous_amount);
        total_current += flt(row.current_amount);
        total_todate += flt(row.todate_amount);
    });

    frm.set_value("p_total", total_previous);
    frm.set_value("c_total", total_current);
    frm.set_value("t_total", total_todate);

    frm.set_value("p_vat", total_previous * 0.15);
    frm.set_value("c_vat", total_current * 0.15);
    frm.set_value("t_vat", total_todate * 0.15);

    frm.set_value("p_total_vat", total_previous * 1.15);
    frm.set_value("c_total_vat", total_current * 1.15);
    frm.set_value("t_total_vat", total_todate * 1.15);

}

function update_summary(frm) {
    if (!frm.doc.items || !frm.doc.items.length) {
        frm.doc.summary = [];
        frm.refresh_field("summary");
        return;
    }

    let summary_map = {};
    console.log("sth new is here");

    frm.doc.items.forEach(item => {
        let task_group = item.task_group;
        let previous_amount = flt(item.p_amount);
        let current_amount = flt(item.c_amount);
        let total_amount = previous_amount + current_amount;
        let contract_amount = flt(item.amount);

        if (task_group) {
            if (!summary_map[task_group]) {
                summary_map[task_group] = {
                    task_group: task_group,
                    previous_amount: 0,
                    current_amount: 0,
                    todate_amount: 0,
                    contract_amount: 0
                };
            }

            summary_map[task_group].previous_amount += previous_amount;
            summary_map[task_group].current_amount += current_amount;
            summary_map[task_group].todate_amount += total_amount;
            summary_map[task_group].contract_amount += contract_amount;
        }
    });

    let updated_summary = Object.values(summary_map);
    console.log("updated_summary", updated_summary);

    frm.doc.summary = [];

    updated_summary.forEach(item => {
        let row = frm.add_child("summary");
        row.task_group = item.task_group;
        row.previous_amount = item.previous_amount;
        row.current_amount = item.current_amount;
        row.todate_amount = item.todate_amount;
        row.contract_amount = item.contract_amount;
    });

    frm.refresh_field("summary");
}