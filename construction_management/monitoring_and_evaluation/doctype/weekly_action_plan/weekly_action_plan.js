// Copyright (c) 2026, Antigravity and contributors
// For license information, please see license.txt

frappe.ui.form.on('Weekly Action Plan', {
	setup: function (frm) {
		const resource_tables = ['manpower_items', 'material_items', 'equipment_items', 'subcontractor_items'];
		resource_tables.forEach(table => {
			frm.set_query('activity', table, function() {
				let activities = (frm.doc.action_plan_items || []).map(row => row.activity).filter(a => !!a);
				return {
					filters: {
						name: ['in', activities]
					}
				};
			});
		});

		frm.set_query('activity', 'action_plan_items', function() {
			return { filters: { project: frm.doc.project } };
		});
	},
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Create Daily Report'), function() {
				let drr_doc = frappe.model.get_new_doc("Daily Resource Report");
				drr_doc.project = frm.doc.project;
				drr_doc.weekly_action_plan = frm.doc.name;
				drr_doc.date = frappe.datetime.get_today();
				frappe.set_route("Form", "Daily Resource Report", drr_doc.name);
			}, __("Actions"));

			frm.add_custom_button(__('Create Timesheets (Revenue)'), function() {
				frappe.call({
					method: 'construction_management.monitoring_and_evaluation.doctype.weekly_action_plan.weekly_action_plan.create_timesheets_from_wap',
					args: { wap_name: frm.doc.name },
					freeze: true,
					freeze_message: __('Creating timesheets from weekly plan...'),
					callback(r) {
						const count = (r.message || []).length;
						frappe.show_alert({
							message: __('Created or updated {0} timesheet(s)', [count]),
							indicator: 'green'
						});
						frm.reload_doc();
					}
				});
			}, __("Actions"));

			setup_wap_source_link_buttons(frm);

			frm.add_custom_button(__('Refresh Daily Reports'), function() {
				frappe.call({
					method: 'construction_management.monitoring_and_evaluation.doctype.weekly_action_plan.weekly_action_plan.refresh_daily_summaries',
					args: { wap_name: frm.doc.name },
					callback() {
						frm.reload_doc();
					}
				});
			}, __("Actions"));
		}
	},
	overhead_percentage: function(frm) {
		calculate_summary(frm);
	},
	fuel_price: function(frm) {
		frm.doc.equipment_items.forEach(row => {
			calculate_equipment_cost(frm, row.doctype, row.name);
		});
		calculate_summary(frm);
	},
	action_plan_items_remove: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		const resource_tables = ['manpower_items', 'material_items', 'equipment_items'];
		
		resource_tables.forEach(table_fieldname => {
			let items = frm.doc[table_fieldname] || [];
			for (let i = items.length - 1; i >= 0; i--) {
				if (items[i].action_plan_item_name === row.name) {
					frm.doc[table_fieldname].splice(i, 1);
				}
			}
			frm.refresh_field(table_fieldname);
		});
		
		calculate_summary(frm);
	}
});

frappe.ui.form.on('Weekly Action Plan Item', {
	activity: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.activity) {
			frappe.call({
				method: 'construction_management.monitoring_and_evaluation.doctype.weekly_action_plan.weekly_action_plan.get_cbd_details',
				args: { task: row.activity },
				callback: function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, 'unit_price_share', r.message.total_unit_cost);

						(r.message.materials || []).forEach(m => {
							let child = frm.add_child('material_items');
							frappe.model.set_value(child.doctype, child.name, 'activity', row.activity);
							frappe.model.set_value(child.doctype, child.name, 'item', m.item);
							frappe.model.set_value(child.doctype, child.name, 'unit', m.unit);
							frappe.model.set_value(child.doctype, child.name, 'consumption_rate', m.consumption_rate);
							frappe.model.set_value(child.doctype, child.name, 'unit_price', m.unit_price);
							frappe.model.set_value(child.doctype, child.name, 'action_plan_item_name', row.name);
							calculate_material_amount(frm, child.doctype, child.name);
						});
						frm.refresh_field('material_items');

						(r.message.manpower || []).forEach(m => {
							let child = frm.add_child('manpower_items');
							frappe.model.set_value(child.doctype, child.name, 'activity', row.activity);
							frappe.model.set_value(child.doctype, child.name, 'title', m.designation);
							frappe.model.set_value(child.doctype, child.name, 'no_of_workers', m.no);
							frappe.model.set_value(child.doctype, child.name, 'hours', m.uf);
							frappe.model.set_value(child.doctype, child.name, 'cost_rate', m.cost_rate);
							frappe.model.set_value(child.doctype, child.name, 'action_plan_item_name', row.name);
							calculate_manpower_total(frm, child.doctype, child.name);
						});
						frm.refresh_field('manpower_items');

						(r.message.machinery || []).forEach(m => {
							let child = frm.add_child('equipment_items');
							frappe.model.set_value(child.doctype, child.name, 'activity', row.activity);
							frappe.model.set_value(child.doctype, child.name, 'fuel_rate', m.fuel_rate);
							frappe.model.set_value(child.doctype, child.name, 'rental_rate', m.rental_rate);
							frappe.model.set_value(child.doctype, child.name, 'action_plan_item_name', row.name);
							calculate_equipment_cost(frm, child.doctype, child.name);
						});
						frm.refresh_field('equipment_items');

						calculate_summary(frm);
					}
				}
			});
		}
	},
	qty: function (frm, cdt, cdn) {
		calculate_expected_amount(frm, cdt, cdn);
		let row = locals[cdt][cdn];
		(frm.doc.material_items || []).forEach(mat => {
			if (mat.action_plan_item_name === row.name || (mat.activity === row.activity && !mat.action_plan_item_name)) {
				if (!mat.action_plan_item_name) frappe.model.set_value(mat.doctype, mat.name, 'action_plan_item_name', row.name);
				calculate_material_amount(frm, mat.doctype, mat.name);
			}
		});
		calculate_summary(frm);
	},
	unit_price_share: function (frm, cdt, cdn) {
		calculate_expected_amount(frm, cdt, cdn);
		calculate_summary(frm);
	}
});

frappe.ui.form.on('Weekly Action Plan Manpower', {
	activity: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.activity && !row.action_plan_item_name) {
			let matched = (frm.doc.action_plan_items || []).find(item => item.activity === row.activity);
			if (matched) frappe.model.set_value(cdt, cdn, 'action_plan_item_name', matched.name);
		}
		calculate_manpower_total(frm, cdt, cdn);
	},
	no_of_workers: function (frm, cdt, cdn) {
		calculate_manpower_total(frm, cdt, cdn);
		calculate_summary(frm);
	},
	hours: function (frm, cdt, cdn) {
		calculate_manpower_total(frm, cdt, cdn);
		calculate_summary(frm);
	},
	cost_rate: function (frm, cdt, cdn) {
		calculate_manpower_total(frm, cdt, cdn);
		calculate_summary(frm);
	}
});

frappe.ui.form.on('Weekly Action Plan Equipment', {
	activity: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.activity && !row.action_plan_item_name) {
			let matched = (frm.doc.action_plan_items || []).find(item => item.activity === row.activity);
			if (matched) frappe.model.set_value(cdt, cdn, 'action_plan_item_name', matched.name);
		}
		calculate_equipment_cost(frm, cdt, cdn);
	},
	total_hours: function (frm, cdt, cdn) {
		calculate_equipment_cost(frm, cdt, cdn);
		calculate_summary(frm);
	},
	fuel_rate: function (frm, cdt, cdn) {
		calculate_equipment_cost(frm, cdt, cdn);
		calculate_summary(frm);
	},
	rental_rate: function (frm, cdt, cdn) {
		calculate_equipment_cost(frm, cdt, cdn);
		calculate_summary(frm);
	},
	is_rental: function (frm, cdt, cdn) {
		calculate_equipment_cost(frm, cdt, cdn);
		calculate_summary(frm);
	}
});

frappe.ui.form.on('Weekly Action Plan Material', {
	activity: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.activity && !row.action_plan_item_name) {
			let matched = (frm.doc.action_plan_items || []).find(item => item.activity === row.activity);
			if (matched) frappe.model.set_value(cdt, cdn, 'action_plan_item_name', matched.name);
		}
		calculate_material_amount(frm, cdt, cdn);
	},
	consumption_rate: function (frm, cdt, cdn) {
		calculate_material_amount(frm, cdt, cdn);
		calculate_summary(frm);
	},
	unit_price: function (frm, cdt, cdn) {
		calculate_material_amount(frm, cdt, cdn);
		calculate_summary(frm);
	},
	total_qty: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'amount', flt(row.total_qty) * flt(row.unit_price));
		calculate_summary(frm);
	}
});

frappe.ui.form.on('Weekly Action Plan Subcontractor', {
	activity: function(frm, cdt, cdn) {
		calculate_subcontractor_amount(frm, cdt, cdn);
	},
	qty: function (frm, cdt, cdn) {
		calculate_subcontractor_amount(frm, cdt, cdn);
		calculate_summary(frm);
	},
	unit_rate: function (frm, cdt, cdn) {
		calculate_subcontractor_amount(frm, cdt, cdn);
		calculate_summary(frm);
	}
});

frappe.ui.form.on('Weekly Action Plan Miscellaneous', {
	amount: function (frm) {
		calculate_summary(frm);
	}
});

var calculate_expected_amount = function (frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, 'expected_amount', flt(row.qty) * flt(row.unit_price_share));
};

var calculate_manpower_total = function (frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	let total_hours = flt(row.no_of_workers) * flt(row.hours);
	frappe.model.set_value(cdt, cdn, 'total_hours', total_hours);
	frappe.model.set_value(cdt, cdn, 'amount', total_hours * flt(row.cost_rate));
};

var calculate_equipment_cost = function (frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	let rental_cost = row.is_rental ? (flt(row.total_hours) * flt(row.rental_rate)) : 0;
	let fuel_cost = flt(row.total_hours) * flt(row.fuel_rate) * flt(frm.doc.fuel_price);
	frappe.model.set_value(cdt, cdn, 'total_cost', rental_cost + fuel_cost);
};

var calculate_material_amount = function (frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	let activity_qty = 0;
	if (row.action_plan_item_name) {
		frm.doc.action_plan_items.forEach(item => {
			if (item.name === row.action_plan_item_name) {
				activity_qty = flt(item.qty);
			}
		});
	} else if (row.activity) {
		let item = (frm.doc.action_plan_items || []).find(i => i.activity === row.activity);
		if (item) {
			activity_qty = flt(item.qty);
		}
	}
	let total_qty = activity_qty * flt(row.consumption_rate);
	frappe.model.set_value(cdt, cdn, 'total_qty', total_qty);
	frappe.model.set_value(cdt, cdn, 'amount', total_qty * flt(row.unit_price));
};

var calculate_subcontractor_amount = function (frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, 'amount', flt(row.qty) * flt(row.unit_rate));
};

var calculate_summary = function (frm) {
	let total_revenue = 0;
	let total_cost = 0;

	frm.doc.action_plan_items.forEach(row => { total_revenue += flt(row.expected_amount); });
	
	frm.doc.manpower_items.forEach(row => { total_cost += flt(row.amount); });
	frm.doc.material_items.forEach(row => { total_cost += flt(row.amount); });
	frm.doc.equipment_items.forEach(row => { total_cost += flt(row.total_cost); });
	frm.doc.subcontractor_items.forEach(row => { total_cost += flt(row.amount); });
	frm.doc.miscellaneous_items.forEach(row => { total_cost += flt(row.amount); });

	let overhead_amount = total_revenue * (flt(frm.doc.overhead_percentage) / 100);
	let projected_profit = total_revenue - total_cost - overhead_amount;

	frm.set_value('total_revenue', total_revenue);
	frm.set_value('total_cost', total_cost);
	frm.set_value('overhead_amount', overhead_amount);
	frm.set_value('projected_profit', projected_profit);
};

function setup_wap_source_link_buttons(frm) {
	const configs = [
		{ table: 'timesheet_entries', field: 'timesheet', doctype: 'Timesheet', group: __('Timesheets') },
		{ table: 'daily_summaries', field: 'daily_resource_report', doctype: 'Daily Resource Report', group: __('Daily Reports') },
	];

	configs.forEach((cfg) => {
		const seen = new Set();
		(frm.doc[cfg.table] || []).forEach((row) => {
			const docname = row[cfg.field];
			if (!docname || seen.has(docname)) return;
			seen.add(docname);
			frm.add_custom_button(`${cfg.doctype}: ${docname}`, () => {
				frappe.set_route('Form', cfg.doctype, docname);
			}, cfg.group);
		});
	});
}
