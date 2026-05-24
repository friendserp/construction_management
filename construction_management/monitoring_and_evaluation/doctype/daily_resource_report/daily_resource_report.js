// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Daily Resource Report', {
	setup(frm) {
		frm.set_query('weekly_action_plan', () => {
			const filters = { project: frm.doc.project, docstatus: 1 };
			if (frm.doc.date) {
				filters.from_date = ['<=', frm.doc.date];
				filters.to_date = ['>=', frm.doc.date];
			}
			return { filters };
		});
	},

	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Refresh Actuals'), () => fetch_totals(frm));
		}
		setup_source_link_buttons(frm);
	},

	project(frm) {
		if (frm.doc.project && frm.doc.date && !frm.doc.weekly_action_plan) {
			auto_select_weekly_plan(frm);
		}
		fetch_totals(frm);
	},

	date(frm) {
		if (frm.doc.project && frm.doc.date && !frm.doc.weekly_action_plan) {
			auto_select_weekly_plan(frm);
		}
		fetch_totals(frm);
	},

	weekly_action_plan(frm) {
		fetch_totals(frm);
	},
});

function auto_select_weekly_plan(frm) {
	frappe.call({
		method: 'construction_management.monitoring_and_evaluation.doctype.daily_resource_report.daily_resource_report.get_weekly_plans_for_project',
		args: { project: frm.doc.project, date: frm.doc.date },
		callback(r) {
			if (r.message && r.message.length === 1) {
				frm.set_value('weekly_action_plan', r.message[0].name);
			}
		},
	});
}

function _table_button_group(table) {
	const labels = {
		labor_details: __('Labor Sources'),
		material_details: __('Material Issues'),
		equipment_details: __('Equipment Reports'),
		revenue_details: __('Timesheets'),
	};
	return labels[table] || __('Sources');
}

const SOURCE_LINK_CONFIG = {
	labor_details: { field: 'source_document', doctype: 'Daily Cost Report', label: 'Daily Cost Report' },
	material_details: { field: 'stock_entry', doctype: 'Stock Entry', label: 'Stock Entry' },
	equipment_details: { field: 'source_document', doctype: 'Equipment Expense Report', label: 'Equipment Expense Report' },
	revenue_details: { field: 'timesheet', doctype: 'Timesheet', label: 'Timesheet' },
};

function setup_source_link_buttons(frm) {
	Object.entries(SOURCE_LINK_CONFIG).forEach(([table, cfg]) => {
		const seen = new Set();
		(frm.doc[table] || []).forEach((row) => {
			const docname = row[cfg.field];
			if (!docname || seen.has(docname)) return;
			seen.add(docname);
			frm.add_custom_button(__(cfg.label) + ': ' + docname, () => {
				frappe.set_route('Form', cfg.doctype, docname);
			}, _table_button_group(table));
		});
	});
}

function fetch_totals(frm) {
	if (!frm.doc.project || !frm.doc.date) return;

	frm.call({
		method: 'fetch_totals',
		doc: frm.doc,
		freeze: true,
		freeze_message: __('Fetching actuals from source documents...'),
		callback(r) {
			if (!r.message) return;
			const table_fields = ['labor_details', 'material_details', 'equipment_details', 'revenue_details'];
			Object.keys(r.message).forEach((fieldname) => {
				if (table_fields.includes(fieldname)) {
					frm.clear_table(fieldname);
					(r.message[fieldname] || []).forEach((row) => {
						const child = frm.add_child(fieldname);
						Object.assign(child, row);
					});
					frm.refresh_field(fieldname);
				} else {
					frm.set_value(fieldname, r.message[fieldname]);
				}
			});
		},
	});
}
