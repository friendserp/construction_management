// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('CBD', {
    productivity(frm) {
        calculate_total_unit_cost(frm)
    },
    validate(frm) {
        calculate_total_unit_cost(frm);
    }
});

frappe.ui.form.on('CBD Material', {
    qty(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    }
});

frappe.ui.form.on('CBD Manpower', {
    no(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    },
    uf(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    },
    indexed_hourly_cost(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    }
});

frappe.ui.form.on('CBD Machinery', {
    no(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    },
    hourly_rental(frm, cdt, cdn) {
        calculate_unit_cost(frm, cdt, cdn);
    }
});

function calculate_unit_cost(frm, cdt, cdn) {
    let child = locals[cdt][cdn];

    if (child.doctype === "CBD Material") {
        child.cost_per_unit = (child.qty || 0) * (child.rate || 0);
    } 
    else if (child.doctype === "CBD Manpower") {
        child.hourly_cost = (child.no || 0) * (child.uf || 0) * (child.indexed_hourly_cost || 0);
    } 
    else if (child.doctype === "CBD Machinery") {
        child.hourly_cost = (child.no || 0) * (child.hourly_rental || 0);
    }

    frm.refresh_field("materials");
    frm.refresh_field("manpowers");
    frm.refresh_field("machineries");

    // Calculate total unit cost
    calculate_total_unit_cost(frm);
}

function calculate_total_unit_cost(frm) {
    let material_unit_cost = 0;
    let manpower_unit_cost = 0;
    let machinery_unit_cost = 0;
    let productivity = frm.doc.productivity || 1; // Ensure productivity is a valid number

    // Sum up Material costs
    if (frm.doc.materials) {
        frm.doc.materials.forEach(row => {
            material_unit_cost += (row.cost_per_unit || 0) / productivity;
        });
    }

    // Sum up Manpower costs
    if (frm.doc.manpowers) {
        frm.doc.manpowers.forEach(row => {
            manpower_unit_cost += (row.hourly_cost || 0) / productivity;
        });
    }

    // Sum up Machinery costs
    if (frm.doc.machineries) {
        frm.doc.machineries.forEach(row => {
            machinery_unit_cost += (row.hourly_cost || 0) / productivity;
        });
    }

    // Compute total unit cost
    frm.set_value("material_unit_cost", material_unit_cost);
    frm.set_value("manpower_unit_cost", manpower_unit_cost);
    frm.set_value("machinery_unit_cost", machinery_unit_cost);
    frm.set_value("direct_cost", material_unit_cost + manpower_unit_cost + machinery_unit_cost);
    frm.set_value("total_unit_cost", material_unit_cost + manpower_unit_cost + machinery_unit_cost);

    frm.refresh_field("material_unit_cost");
    frm.refresh_field("manpower_unit_cost");
    frm.refresh_field("machinery_unit_cost");
    frm.refresh_field("total_unit_cost");
}

