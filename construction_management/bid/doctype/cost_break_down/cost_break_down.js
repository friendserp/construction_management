// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cost Break Down', {
	hourly_output_mp: function (frm) {
		calculate_all(frm);
	},
	hourly_output_eq: function (frm) {
		calculate_all(frm);
	},
	overhead_cost: function (frm) {
		calculate_all(frm);
	},
	profit_cost: function (frm) {
		calculate_all(frm);
	},
	validate: function (frm) {
		calculate_all(frm);
	}
});

frappe.ui.form.on('CBD Material', {
	qty: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'cost_per_unit', flt(row.qty) * flt(row.rate));
		calculate_all(frm);
	},
	rate: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'cost_per_unit', flt(row.qty) * flt(row.rate));
		calculate_all(frm);
	},
	materials_remove: function (frm) {
		calculate_all(frm);
	}
});

frappe.ui.form.on('CBD Manpower', {
	no: function (frm, cdt, cdn) {
		calculate_manpower_row(frm, cdt, cdn);
	},
	uf: function (frm, cdt, cdn) {
		calculate_manpower_row(frm, cdt, cdn);
	},
	indexed_hourly_cost: function (frm, cdt, cdn) {
		calculate_manpower_row(frm, cdt, cdn);
	},
	manpowers_remove: function (frm) {
		calculate_all(frm);
	}
});

frappe.ui.form.on('CBD Machinery', {
	no: function (frm, cdt, cdn) {
		calculate_machinery_row(frm, cdt, cdn);
	},
	uf: function (frm, cdt, cdn) {
		calculate_machinery_row(frm, cdt, cdn);
	},
	hourly_rental: function (frm, cdt, cdn) {
		calculate_machinery_row(frm, cdt, cdn);
	},
	machineries_remove: function (frm) {
		calculate_all(frm);
	}
});

var calculate_manpower_row = function (frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, 'hourly_cost', flt(row.no) * flt(row.uf) * flt(row.indexed_hourly_cost));
	calculate_all(frm);
};

var calculate_machinery_row = function (frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, 'hourly_cost', flt(row.no) * flt(row.uf) * flt(row.hourly_rental));
	calculate_all(frm);
};

var calculate_all = function (frm) {
	let material_total = 0;
	let manpower_total = 0;
	let machinery_total = 0;

	(frm.doc.materials || []).forEach(row => {
		material_total += flt(row.cost_per_unit);
	});

	(frm.doc.manpowers || []).forEach(row => {
		manpower_total += flt(row.hourly_cost);
	});

	(frm.doc.machineries || []).forEach(row => {
		machinery_total += flt(row.hourly_cost);
	});

	// Manpower / Machinery are per hour, so divide by their hourly output.
	// Material hourly output is 1 by default, so its total == its unit cost.
	let manpower_output = flt(frm.doc.hourly_output_mp) || 1;
	let machinery_output = flt(frm.doc.hourly_output_eq) || 1;

	let material_unit_cost = material_total;
	let manpower_unit_cost = manpower_total / manpower_output;
	let machinery_unit_cost = machinery_total / machinery_output;

	frm.set_value('total_material_cost', material_total);
	frm.set_value('total_manpower_cost', manpower_total);
	frm.set_value('total_machinery_cost', machinery_total);

	frm.set_value('material_unit_cost', material_unit_cost);
	frm.set_value('manpower_unit_cost', manpower_unit_cost);
	frm.set_value('machinery_unit_cost', machinery_unit_cost);

	let direct_cost = material_unit_cost + manpower_unit_cost + machinery_unit_cost;
	frm.set_value('direct_cost', direct_cost);

	let total_unit_cost = direct_cost + flt(frm.doc.overhead_cost) + flt(frm.doc.profit_cost);
	frm.set_value('total_unit_cost', total_unit_cost);
};

