// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Price Escalation Claim', {
	setup: function(frm) {
		// Set queries if needed
	},
	refresh: function(frm) {
		// Add custom buttons if needed
	}
});

// Reinf Detail Triggers
frappe.ui.form.on('Reinf Escalation Detail', {
	total_work_qty: function(frm, cdt, cdn) { calculate_reinf(frm, cdt, cdn); },
	prev_qty: function(frm, cdt, cdn) { calculate_reinf(frm, cdt, cdn); },
	qty_per_unit: function(frm, cdt, cdn) { calculate_reinf(frm, cdt, cdn); },
	current_price: function(frm, cdt, cdn) { calculate_reinf(frm, cdt, cdn); },
	initial_price: function(frm, cdt, cdn) { calculate_reinf(frm, cdt, cdn); }
});

function calculate_reinf(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	row.net_qty = (row.total_work_qty || 0) - (row.prev_qty || 0);
	row.total_escalation_qty = row.net_qty * (row.qty_per_unit || 0);
	row.cost_variation = ( (row.current_price || 0) - (row.initial_price || 0) ) * row.total_escalation_qty;
	frm.refresh_field('reinf_details');
}

// Cement Detail Triggers
frappe.ui.form.on('Cement Escalation Detail', {
	total_work_qty: function(frm, cdt, cdn) { calculate_cement(frm, cdt, cdn); },
	prev_qty: function(frm, cdt, cdn) { calculate_cement(frm, cdt, cdn); },
	qty_per_unit: function(frm, cdt, cdn) { calculate_cement(frm, cdt, cdn); },
	current_price: function(frm, cdt, cdn) { calculate_cement(frm, cdt, cdn); },
	initial_price: function(frm, cdt, cdn) { calculate_cement(frm, cdt, cdn); }
});

function calculate_cement(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	row.net_qty = (row.total_work_qty || 0) - (row.prev_qty || 0);
	row.total_escalation_qty = row.net_qty * (row.qty_per_unit || 0);
	row.cost_variation = ( (row.current_price || 0) - (row.initial_price || 0) ) * row.total_escalation_qty;
	frm.refresh_field('cement_details');
}

// Fuel Detail Triggers
frappe.ui.form.on('Fuel Escalation Detail', {
	type: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); },
	trip_distance: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); },
	fuel_per_km: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); },
	consumption_per_hr: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); },
	quantity: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); },
	current_price: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); },
	initial_price: function(frm, cdt, cdn) { calculate_fuel(frm, cdt, cdn); }
});

function calculate_fuel(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (row.type == "Truck") {
		row.total_fuel_consumed = (row.trip_distance || 0) * (row.fuel_per_km || 0) * (row.quantity || 0);
	} else {
		row.total_fuel_consumed = (row.consumption_per_hr || 0) * (row.quantity || 0);
	}
	row.cost_variation = ( (row.current_price || 0) - (row.initial_price || 0) ) * row.total_fuel_consumed;
	frm.refresh_field('fuel_details');
}
