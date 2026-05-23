// Copyright (c) 2026, Sami and contributors
// For license information, please see license.txt

frappe.ui.form.on('Equipment Expense Report', {
	setup: function(frm) {
		// Set query filters or configurations here if needed
	}
});

frappe.ui.form.on('Equipment Expense Detail', {
	prev_op_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	prev_id_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	prev_d_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	prev_mob_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	
	current_op_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	current_id_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	current_d_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	current_mob_hr: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	
	rental_rate_op: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); },
	rental_rate_idle: function(frm, cdt, cdn) { calculate_row(frm, cdt, cdn); }
});

function calculate_row(frm, cdt, cdn) {
	let row = locals[cdt][cdn];

	// 1. Calculate to-date hours
	row.todate_op_hr = (row.prev_op_hr || 0.0) + (row.current_op_hr || 0.0);
	row.todate_id_hr = (row.prev_id_hr || 0.0) + (row.current_id_hr || 0.0);
	row.todate_d_hr = (row.prev_d_hr || 0.0) + (row.current_d_hr || 0.0);
	row.todate_mob_hr = (row.prev_mob_hr || 0.0) + (row.current_mob_hr || 0.0);

	// 2. Previous Period Expenses
	row.prev_op_expense = (row.prev_op_hr || 0.0) * (row.rental_rate_op || 0.0);
	row.prev_idle_expense = (row.prev_id_hr || 0.0) * (row.rental_rate_idle || 0.0);
	row.prev_total_expense = row.prev_op_expense + row.prev_idle_expense;

	// 3. Current Period Expenses
	row.current_op_expense = (row.current_op_hr || 0.0) * (row.rental_rate_op || 0.0);
	row.current_idle_expense = (row.current_id_hr || 0.0) * (row.rental_rate_idle || 0.0);
	row.current_total_expense = row.current_op_expense + row.current_idle_expense;

	// 4. To Date Expenses (Cumulative)
	row.todate_op_expense = row.prev_op_expense + row.current_op_expense;
	row.todate_idle_expense = row.prev_idle_expense + row.current_idle_expense;
	row.todate_total_expense = row.todate_op_expense + row.todate_idle_expense;

	frm.refresh_field('equipment_entries');
	calculate_grand_totals(frm);
}

function calculate_grand_totals(frm) {
	let grand_total_prev = 0.0;
	let grand_total_current = 0.0;
	let grand_total_todate = 0.0;

	if (frm.doc.equipment_entries) {
		frm.doc.equipment_entries.forEach(row => {
			grand_total_prev += (row.prev_total_expense || 0.0);
			grand_total_current += (row.current_total_expense || 0.0);
			grand_total_todate += (row.todate_total_expense || 0.0);
		});
	}

	frm.set_value('grand_total_prev', grand_total_prev);
	frm.set_value('grand_total_current', grand_total_current);
	frm.set_value('grand_total_todate', grand_total_todate);
}
