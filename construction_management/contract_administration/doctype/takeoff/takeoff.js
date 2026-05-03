frappe.ui.form.on('Takeoff', {
    before_save(frm) {
        update_summary(frm);
    },

    boq(frm) {
        if (!frm.doc.boq) return;

        frm.clear_table("items");

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "BOQ",
                name: frm.doc.boq
            },
            callback: function (response) {
                if (response.message) {
                    let items = response.message.items || [];

                    items.forEach(item => {
                        let row = frm.add_child("items");
                        row.task_group = item.task_group;
                        row.work_item = item.item_work;
                        row.description = item.description;
                        row.unit = item.unit;
                    });

                    frm.refresh_field("items");
                    update_summary(frm);
                }
            }
        });
    }
});

frappe.ui.form.on('Takeoff Items', {
    d1(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },

    d2(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },

    d3(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },

    qty(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },

    items_remove(frm) {
        update_summary(frm);
    }
});

function calculate_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let d1 = flt(row.d1 || 1);
    let d2 = flt(row.d2 || 1);
    let d3 = flt(row.d3 || 1);
    let qty = flt(row.qty || 1);

    let total = d1 * d2 * d3 * qty;

    frappe.model.set_value(cdt, cdn, "total_quantity", total);

    update_summary(frm);
}

function update_summary(frm) {
    if (!frm.doc.items || !frm.doc.items.length) {
        frm.clear_table("summary");
        frm.refresh_field("summary");
        return;
    }

    let summary_map = {};

    frm.doc.items.forEach(item => {
        let task_group = item.task_group;
        let total_quantity = flt(item.total_quantity);

        if (task_group && total_quantity) {
            if (!summary_map[task_group]) {
                summary_map[task_group] = {
                    group_task: task_group,
                    qty: 0
                };
            }

            summary_map[task_group].qty += total_quantity;
        }
    });

    frm.clear_table("summary");

    Object.values(summary_map).forEach(data => {
        let row = frm.add_child("summary");
        row.group_task = data.group_task;
        row.qty = data.qty;
    });

    frm.refresh_field("summary");
}