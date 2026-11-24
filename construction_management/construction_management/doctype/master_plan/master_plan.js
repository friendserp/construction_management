// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

const NS = "construction_management.construction_management.doctype.master_plan.master_plan";

const RP_MACHINE_KEYS = ["doz", "exc", "grader", "loader", "dt"];
const RP_MACHINE_TABLE_FIELDS = {
	doz: "resource_doz_tasks",
	exc: "resource_exc_tasks",
	grader: "resource_grader_tasks",
	loader: "resource_loader_tasks",
	dt: "resource_dt_tasks",
};
const RP_DT_FIELDS = ["distance", "speed", "load_unload_min", "capacity", "efficiency", "availability", "loose_factor"];

function get_view_year(frm) {
	const year = String(frm.doc.planning_year || "");
	return /^\d{4}$/.test(year) ? year : "";
}

function setup_planning_year(frm) {
	const years = [];
	if (frm.doc.start_date && frm.doc.end_date) {
		const start = frappe.datetime.str_to_obj(frm.doc.start_date).getFullYear();
		const end = frappe.datetime.str_to_obj(frm.doc.end_date).getFullYear();
		for (let y = start; y <= end; y++) years.push(String(y));
	}
	frm.set_df_property("planning_year", "options", [__("All Years")].concat(years).join("\n"));
	const current = String(frm.doc.planning_year || "");
	if (/^\d{4}$/.test(current) && years.indexOf(current) === -1) {
		frm.set_value("planning_year", __("All Years"));
	} else {
		frm.refresh_field("planning_year");
	}
	return years;
}

function scope_note(frm) {
	const year = get_view_year(frm);
	return year ? __("Viewing {0}", [year]) : __("Viewing all years");
}

function scope_distribution(frm, data) {
	const year = get_view_year(frm);
	if (!year || !data) return data;
	const columns = (data.columns || []).filter((c) => String(c.key).slice(0, 4) === year);
	const keys = {};
	columns.forEach((c) => (keys[c.key] = true));
	const scope_cells = (cells) => {
		const out = {};
		Object.keys(cells || {}).forEach((key) => {
			if (keys[key]) out[key] = cells[key];
		});
		return out;
	};
	const rows = (data.rows || []).map((row) => {
		const cells = scope_cells(row.cells);
		const scoped_qty = columns.reduce((sum, c) => sum + flt(cells[c.key] && cells[c.key].qty), 0);
		return Object.assign({}, row, { cells, distributed_qty: scoped_qty });
	});
	const result = Object.assign({}, data, { columns, rows });
	["machinery", "manpower", "material"].forEach((kind) => {
		result[kind] = (data[kind] || []).map((row) =>
			Object.assign({}, row, { cells: scope_cells(row.cells) })
		);
	});
	return result;
}

function render_cached_distribution(frm) {
	const data = frm.__mp_distribution_data;
	if (!data) return;
	const scoped = scope_distribution(frm, data);
	render_monthly_matrix(frm, scoped);
	render_cost_matrix(frm, scoped);
	render_yearly_matrix(frm, data);
	render_resource_plan(frm, data);
}

// Temporary debug logging for the workload distribution tables.
const MP_DEBUG = true;
function mp_log(label, value) {
	if (!MP_DEBUG) return;
	if (value === undefined) console.log(`[MasterPlan] ${label}`);
	else console.log(`[MasterPlan] ${label}`, value);
}

frappe.ui.form.on("Master Plan", {
	project(frm) {
		if (!frm.doc.project) return;
		rp_reset_state(frm);
		rp_setup_machine_child_queries(frm);
		load_tasks(frm);
		frappe.after_ajax(() => maybe_autobuild_calendar(frm));
	},
	get_task(frm) {
		load_tasks(frm);
	},
	get_calender(frm) {
		build_working_calendar(frm);
	},
	get_monthly_distribution(frm) {
		build_monthly_distribution(frm);
	},
	run_schedule(frm) {
		run_schedule_engine(frm);
	},
	season_length_months(frm) {
		if (frm.doc.start_date && frm.doc.end_date) schedule_recompute(frm);
	},
	start_date(frm) { setup_planning_year(frm); },
	end_date(frm) { setup_planning_year(frm); },
	planning_year(frm) { render_cached_distribution(frm); },
	validate(frm) {
		validate_distribution_totals(frm, { throw: true });
	},
	refresh(frm) {
		frm.__mp_distribution_data = null;
		frm.__mp_resource_computed = null;
		frm.__mp_machine_tables_hydrated = false;
		setup_planning_year(frm);
		rp_setup_machine_child_queries(frm);
		if (!frm.doc.project) {
			frm.dashboard.set_headline(
				__("Select a Project to load tasks and build the Ethiopian holiday calendar.")
			);
			render_working_days_html(frm, html_placeholder(__("Select a Project to build the calendar.")));
			render_matrix_html(frm, html_placeholder(__("Select a Project to build the distribution.")));
			render_cost_matrix(frm, {});
			rp_clear_tabs(frm, __("Select a Project to build resource plans."));
			return;
		}
		if (!frm.doc.start_date || !frm.doc.end_date) {
			frm.dashboard.set_headline(__("Set the project dates to build the holiday calendar."));
			render_working_days_html(frm, html_placeholder(__("Project dates are required.")));
			render_cost_matrix(frm, {});
			rp_clear_tabs(frm, __("Project dates are required."));
			return;
		}
		if (!frm.doc.holiday || !frm.doc.holiday.length) {
			frm.dashboard.set_headline(
				__("No holidays yet. Click '{0}' to load the Ethiopian holidays.", [
					__("Build Calendar, Holidays & Working Days"),
				])
			);
			render_working_days_html(
				frm,
				html_placeholder(
					__("Click '{0}' to load the Ethiopian holidays and build the calendar.", [
						__("Build Calendar, Holidays & Working Days"),
					])
				)
			);
			render_cost_matrix(frm, {});
			rp_clear_tabs(frm, __("Build the working calendar first."));
			return;
		}
		recompute_working_days(frm, { silent: true });
		render_gantt_from_wbs(frm);

		if (frm.doc.wbs && frm.doc.wbs.length) build_monthly_distribution(frm, { silent: true });
	},
});

frappe.ui.form.on("Holidayss", {
	day_type(frm) { schedule_recompute(frm); },
	from_date(frm, cdt, cdn) { set_row_total(frm, cdt, cdn); schedule_recompute(frm); },
	to_date(frm, cdt, cdn) { set_row_total(frm, cdt, cdn); schedule_recompute(frm); },
	holiday_name(frm) { schedule_recompute(frm); },
	holiday_add(frm) { schedule_recompute(frm); },
	holiday_remove(frm) { schedule_recompute(frm); },
});

frappe.ui.form.on("Activity Sequencing", {
	activity(frm) { schedule_recompute(frm); },
	predecessor_activity(frm) { schedule_recompute(frm); },
	relationship_type(frm) { schedule_recompute(frm); },
	lag_days(frm) { schedule_recompute(frm); },
	lead_days(frm) { schedule_recompute(frm); },
	activity_sequencing_remove(frm) { schedule_recompute(frm); },
});

frappe.ui.form.on("WBS", {
	duration(frm) { schedule_recompute(frm); },
});

frappe.ui.form.on("Master Plan Distribution", {
	task_id(frm) { sync_distribution_from_grid(frm); },
	month(frm) { sync_distribution_from_grid(frm); },
	qty(frm) { sync_distribution_from_grid(frm); },
	distribution_remove(frm) { sync_distribution_from_grid(frm); },
});

function rp_on_machine_task_change(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row.task_id) {
		rp_schedule_machine_sync(frm);
		return;
	}
	const dist = ((frm.__mp_distribution_data || {}).rows || []).find(
		(r) => String(r.task_id) === String(row.task_id)
	);
	if (dist) {
		frappe.model.set_value(cdt, cdn, {
			task_name: dist.task_name || "",
			uom: dist.uom || "",
			total_qty: flt(dist.contract_qty),
		});
	} else {
		frappe.db.get_value("Task", row.task_id, ["subject", "custom_unit", "custom_contract_qty"]).then((r) => {
			const task = Array.isArray(r.message) ? (r.message[0] || {}) : (r.message || {});
			frappe.model.set_value(cdt, cdn, {
				task_name: task.subject || "",
				uom: task.custom_unit || "",
				total_qty: flt(task.custom_contract_qty),
			});
		});
	}
	rp_schedule_machine_sync(frm);
}

function rp_setup_machine_child_queries(frm) {
	if (!frm.doc.project) return;
	RP_MACHINE_KEYS.forEach((tab) => {
		const field = RP_MACHINE_TABLE_FIELDS[tab];
		if (!frm.get_field(field)) return;
		frm.set_query("task_id", field, () => ({
			filters: {
				project: frm.doc.project,
				status: ["!=", "Cancelled"],
				is_group: 0,
			},
		}));
	});
}

frappe.ui.form.on("Master Plan Machine Task", {
	task_id(frm, cdt, cdn) { rp_on_machine_task_change(frm, cdt, cdn); },
	eng_pct(frm) { rp_schedule_machine_sync(frm); },
	hours_day(frm) { rp_schedule_machine_sync(frm); },
	hourly_output(frm) { rp_schedule_machine_sync(frm); },
});

frappe.ui.form.on("Master Plan DT Task", {
	task_id(frm, cdt, cdn) { rp_on_machine_task_change(frm, cdt, cdn); },
	eng_pct(frm) { rp_schedule_machine_sync(frm); },
	distance(frm) { rp_schedule_machine_sync(frm); },
	speed(frm) { rp_schedule_machine_sync(frm); },
	load_unload_min(frm) { rp_schedule_machine_sync(frm); },
	capacity(frm) { rp_schedule_machine_sync(frm); },
	efficiency(frm) { rp_schedule_machine_sync(frm); },
	availability(frm) { rp_schedule_machine_sync(frm); },
	loose_factor(frm) { rp_schedule_machine_sync(frm); },
	hours_day(frm) { rp_schedule_machine_sync(frm); },
});

RP_MACHINE_KEYS.forEach((tab) => {
	const field = RP_MACHINE_TABLE_FIELDS[tab];
	const handlers = {
		[`${field}_add`](frm) { rp_schedule_machine_sync(frm); },
		[`${field}_remove`](frm) { rp_schedule_machine_sync(frm); },
	};
	frappe.ui.form.on("Master Plan", handlers);
});

let distribution_rebuild_timer = null;
function sync_distribution_from_grid(frm) {
	if (!validate_distribution_totals(frm, { throw: false })) return;
	clearTimeout(distribution_rebuild_timer);
	distribution_rebuild_timer = setTimeout(
		() => build_monthly_distribution(frm, { silent: true }),
		500
	);
}

function validate_distribution_totals(frm, opts = {}) {
	const contract = {};
	const names = {};
	(frm.doc.wbs || []).forEach((row) => {
		if (!row.task_id) return;
		contract[row.task_id] = flt(row.contract_qty);
		names[row.task_id] = row.task_name || row.task_id;
	});

	const totals = {};
	(frm.doc.distribution || []).forEach((row) => {
		if (!row.task_id || !row.month) return;
		totals[row.task_id] = (totals[row.task_id] || 0) + flt(row.qty);
	});

	for (const task_id in totals) {
		const qty = contract[task_id];
		if (!qty) continue;
		if (totals[task_id] > qty + 0.000000001) {
			const message = __(
				"Task {0}: distributed qty {1} exceeds the total qty {2}.",
				[names[task_id] || task_id, totals[task_id], qty]
			);
			if (opts.throw) frappe.throw(message);
			frappe.msgprint({ message, indicator: "red", title: __("Quantity exceeded") });
			return false;
		}
	}
	return true;
}

function set_row_total(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row || !row.from_date) return;
	const start = frappe.datetime.str_to_obj(row.from_date);
	const end = frappe.datetime.str_to_obj(row.to_date || row.from_date);
	const lo = Math.min(start, end);
	const hi = Math.max(start, end);
	const days = Math.round((hi - lo) / 86400000) + 1;
	frappe.model.set_value(cdt, cdn, "total", days);
}

// ---------------------------------------------------------------------------
// WBS + yearly roll-up
// ---------------------------------------------------------------------------
function load_tasks(frm) {
	if (!frm.doc.project) {
		frappe.msgprint(__("Please select a Project first"));
		return Promise.resolve();
	}
	return frappe
		.call({
			method: `${NS}.get_project_tasks`,
			args: { project: frm.doc.project },
			freeze: true,
			freeze_message: __("Loading tasks..."),
		})
		.then((r) => {
			const tasks = r.message || [];
			if (!tasks.length) {
				frappe.msgprint(__("No tasks found for project {0}", [frm.doc.project]));
				return;
			}
			frm.clear_table("wbs");
			const seen = new Set();
			tasks.forEach((t) => {
				if (!t.name || seen.has(t.name)) return;
				seen.add(t.name);
				const row = frm.add_child("wbs");
				row.task_id = t.name;
				row.task_name = t.subject;
				row.uom = t.custom_unit;
				row.contract_qty = t.custom_contract_qty;
				row.task_unit_rate = t.custom_unit_rate;
				row.amount = t.custom_contract_amount;
				row.duration = flt(t.task_duration_in_days) || flt(t.duration);
				row.start_date = t.exp_start_date;
				row.finish_date = t.exp_end_date;
				row.executed_qty = t.custom_todate_exexuted_qty;
				row.remaining_qty = flt(t.custom_contract_qty) - flt(t.custom_todate_exexuted_qty);
			});
			frm.refresh_field("wbs");
			frm.dirty();
			rp_reset_state(frm);
			frappe.show_alert({ message: __("{0} task(s) loaded", [seen.size]), indicator: "green" });
			build_monthly_distribution(frm, { silent: true });
			maybe_auto_schedule(frm);
		});
}

function render_yearly_matrix(frm, data) {
	const field = frm.get_field("yearly_distribution_html");
	if (!field || !field.$wrapper) return;
	const cols = (data && data.columns) || [];
	const rows = (data && data.rows) || [];
	if (!cols.length || !rows.length) {
		field.$wrapper.html(html_placeholder(
			__("Nothing to distribute yet. Load tasks and build the distribution first.")
		));
		return;
	}
	const years = Array.from(new Set(cols.map((c) => String(c.key).slice(0, 4)))).sort();
	const year_wd = {};
	years.forEach((y) => (year_wd[y] = 0));
	cols.forEach((c) => (year_wd[String(c.key).slice(0, 4)] += flt(c.working_days)));

	const year_head = years
		.map((y) => `<th style="${DIST_TH}text-align:right">${frappe.utils.escape_html(y)}</th>`)
		.join("");
	const wd_cells = years.map((y) => `<td style="${DIST_WD}">${year_wd[y] || ""}</td>`).join("");

	const col_total = {};
	years.forEach((y) => (col_total[y] = 0));

	const body = rows.map((r, i) => {
		const per_year = {};
		years.forEach((y) => (per_year[y] = { qty: 0, amount: 0 }));
		cols.forEach((c) => {
			const cell = r.cells && r.cells[c.key];
			if (!cell) return;
			const y = String(c.key).slice(0, 4);
			per_year[y].qty += flt(cell.qty);
			per_year[y].amount += flt(cell.amount);
		});
		const cells = years.map((y) => {
			const g = per_year[y];
			col_total[y] += g.qty;
			const pct = flt(r.contract_qty) ? (g.qty * 100) / flt(r.contract_qty) : 0;
			const title = `${y}: ${fmt_num(g.qty)} (${fmt_num(pct, 1)}%) · ${fmt_num(g.amount)}`;
			return `<td title="${title}" style="${DIST_TD}text-align:right;${g.qty ? heat_style(pct) : ""
				}">${g.qty ? fmt_num(g.qty) : ""}</td>`;
		}).join("");
		return `<tr>` +
			`<td style="${DIST_TD}color:#94a3b8">${frappe.utils.escape_html(r.series || r.task_id || String(i + 1))}</td>` +
			`<td style="${DIST_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${frappe.utils.escape_html(r.task_name || r.task_id || "")}">${frappe.utils.escape_html(r.task_name || r.task_id || "")}</td>` +
			`<td style="${DIST_TD}white-space:nowrap">${frappe.utils.escape_html(r.uom || "")}</td>` +
			`<td style="${DIST_TD}text-align:right;font-weight:600">${fmt_num(r.contract_qty)}</td>` +
			cells +
			`<td style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(r.distributed_qty)}</td>` +
			"</tr>";
	}).join("");

	const foot = years.map((y) =>
		`<td style="${DIST_TF}text-align:right">${col_total[y] ? fmt_num(col_total[y], 2) : ""}</td>`
	).join("");
	const grand = rows.reduce((s, r) => s + flt(r.distributed_qty), 0);
	const wd_grand = years.reduce((s, y) => s + flt(year_wd[y]), 0);

	field.$wrapper.html(
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
		'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
		`<b>${__("Yearly Workload Distribution")}</b> · ${rows.length} ${__("items")} · ${years.length} ${__("year(s)")} · ` +
		`<span style="color:#64748b">${__("read-only roll-up of the monthly plan")}</span></div>` +
		'<div style="overflow:auto;max-height:75vh">' +
		'<table style="border-collapse:collapse;font-size:12px;width:100%">' +
		"<thead>" +
		`<tr><th style="${DIST_TH}text-align:left">${__("Item")}</th>` +
		`<th style="${DIST_TH}text-align:left">${__("Description")}</th>` +
		`<th style="${DIST_TH}">${__("Unit")}</th>` +
		`<th style="${DIST_TH}text-align:right">${__("Project Qty")}</th>` +
		year_head +
		`<th style="${DIST_TH}text-align:right">${__("TOTAL")}</th></tr>` +
		"</thead>" +
		"<tbody>" +
		`<tr><td colspan="4" style="${DIST_WD_LBL}">${__("Working days per year")}</td>${wd_cells}<td style="${DIST_WD}font-weight:700">${wd_grand}</td></tr>` +
		body +
		"</tbody>" +
		`<tfoot><tr><td colspan="4" style="${DIST_TF}font-weight:600">${__("Total")}</td>${foot}<td style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(grand)}</td></tr></tfoot>` +
		"</table></div></div>"
	);
}

// ---------------------------------------------------------------------------
// Cost distribution
// ---------------------------------------------------------------------------
function render_cost_matrix(frm, data) {
	const field = frm.get_field("cost_distribution_html");
	if (!field || !field.$wrapper) return;
	const cols = (data && data.columns) || [];
	const rows = (data && data.rows) || [];
	if (!cols.length || !rows.length) {
		field.$wrapper.html(html_placeholder(__("Nothing to cost yet. Load tasks and build the distribution first.")));
		return;
	}
	const esc = frappe.utils.escape_html;
	const groups = [];
	cols.forEach((c) => {
		const last = groups[groups.length - 1];
		if (last && last.season === c.season) last.count++;
		else groups.push({ season: c.season, count: 1 });
	});
	const season_cells = groups.map((g) =>
		`<th colspan="${g.count}" style="${DIST_TH}text-align:center">${esc(g.season || "")}</th>`
	).join("");
	const month_cells = cols.map((c) =>
		`<th style="${DIST_TH}white-space:nowrap">${esc(c.label)}</th>`
	).join("");

	const col_total = {};
	cols.forEach((c) => (col_total[c.key] = 0));

	const body = rows.map((r, i) => {
		const rate = flt(r.unit_rate);
		const cells = cols.map((c) => {
			const cell = r.cells ? r.cells[c.key] : null;
			const qty = cell ? flt(cell.qty) : 0;
			const amount = cell && cell.amount != null ? flt(cell.amount) : qty * rate;
			col_total[c.key] += amount;
			return `<td title="${esc(c.label)}: ${fmt_num(amount)}" style="${DIST_TD}text-align:right">${amount ? fmt_num(amount) : ""}</td>`;
		}).join("");
		const row_total = flt(r.distributed_qty) * rate;
		return "<tr>" +
			`<td style="${DIST_TD}color:#94a3b8">${esc(r.series || r.task_id || String(i + 1))}</td>` +
			`<td style="${DIST_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(r.task_name || r.task_id || "")}">${esc(r.task_name || r.task_id || "")}</td>` +
			`<td style="${DIST_TD}white-space:nowrap">${esc(r.uom || "")}</td>` +
			`<td style="${DIST_TD}text-align:right">${fmt_num(rate)}</td>` +
			`<td style="${DIST_TD}text-align:right;font-weight:600">${fmt_num(r.total_planned_amount)}</td>` +
			cells +
			`<td style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(row_total)}</td>` +
			"</tr>";
	}).join("");

	const grand = rows.reduce((s, r) => s + flt(r.distributed_qty) * flt(r.unit_rate), 0);
	const foot_cells = cols.map((c) =>
		`<td style="${DIST_TF}text-align:right">${col_total[c.key] ? fmt_num(col_total[c.key], 2) : ""}</td>`
	).join("");

	field.$wrapper.html(
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
		'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
		`<b>${__("Cost Distribution")}</b> · ${rows.length} ${__("items")} · ${cols.length} ${__("months")} · ` +
		`${scope_note(frm)} · ` +
		`<span style="color:#64748b">${__("read-only: month quantity × unit rate")}</span></div>` +
		'<div style="overflow:auto;max-height:75vh">' +
		'<table style="border-collapse:collapse;font-size:12px;width:100%">' +
		"<thead>" +
		`<tr><th rowspan="2" style="${DIST_TH}text-align:left">${__("Item")}</th>` +
		`<th rowspan="2" style="${DIST_TH}text-align:left">${__("Description")}</th>` +
		`<th rowspan="2" style="${DIST_TH}">${__("Unit")}</th>` +
		`<th rowspan="2" style="${DIST_TH}text-align:right">${__("Unit Rate")}</th>` +
		`<th rowspan="2" style="${DIST_TH}text-align:right">${__("Project Cost")}</th>` +
		season_cells +
		`<th rowspan="2" style="${DIST_TH}text-align:right">${__("TOTAL")}</th></tr>` +
		`<tr>${month_cells}</tr>` +
		"</thead>" +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="5" style="${DIST_TF}font-weight:600">${__("Total")}</td>${foot_cells}<td style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(grand)}</td></tr></tfoot>` +
		"</table></div></div>"
	);
}

// ---------------------------------------------------------------------------
// Working calendar
// ---------------------------------------------------------------------------
function maybe_autobuild_calendar(frm, tries) {
	tries = tries == null ? 6 : tries;
	if (!frm.doc.project) return;
	if (frm.doc.start_date && frm.doc.end_date) {
		if (!frm.doc.holiday || !frm.doc.holiday.length) build_working_calendar(frm, { silent: true });
		return;
	}
	if (tries > 0) setTimeout(() => maybe_autobuild_calendar(frm, tries - 1), 400);
}

function build_working_calendar(frm, opts = {}) {
	if (!frm.doc.start_date || !frm.doc.end_date) {
		if (!opts.silent) frappe.msgprint(__("Please set the Project Start Date and Project End Date first."));
		return;
	}
	frappe.call({
		method: `${NS}.get_working_calendar`,
		args: {
			holiday_list: frm.doc.holiday_list,
			country: frm.doc.holiday_country || "ET",
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			season_length_months: frm.doc.season_length_months || 4,
		},
		freeze: !opts.silent,
		freeze_message: __("Building working days calendar..."),
		callback(r) {
			const data = r.message;
			if (!data) return;
			frm.clear_table("holiday");
			(data.holidays || []).forEach((h) => {
				const row = frm.add_child("holiday");
				row.day_type = h.day_type || "Holiday";
				row.holiday_name = h.holiday_name;
				row.from_date = h.from_date;
				row.to_date = h.to_date;
				row.total = h.total;
				row.month = h.month;
			});
			frm.refresh_field("holiday");
			apply_working_days(frm, data);
			if (data.country && !frm.doc.holiday_country) frm.set_value("holiday_country", data.country);
			if (data.weekly_off && data.weekly_off.indexOf(",") === -1 && !frm.doc.weekly_off) {
				frm.set_value("weekly_off", data.weekly_off);
			}
			frm.dirty();
			if (!opts.silent) {
				frappe.show_alert({
					message: __("{0} holiday row(s) between {1} and {2}", [
						(data.holidays || []).length, frm.doc.start_date, frm.doc.end_date,
					]),
					indicator: "green",
				});
			}
			if (frm.doc.wbs && frm.doc.wbs.length) {
				build_monthly_distribution(frm, { silent: true });
				if (!opts.silent) maybe_auto_schedule(frm);
			}
		},
	});
}

let recompute_timer = null;
function schedule_recompute(frm) {
	clearTimeout(recompute_timer);
	recompute_timer = setTimeout(() => recompute_working_days(frm), 800);
}

function recompute_working_days(frm, opts = {}) {
	if (!frm.doc.start_date || !frm.doc.end_date) return;
	const holidays = (frm.doc.holiday || []).map((h) => ({
		day_type: h.day_type || "Holiday",
		from_date: h.from_date,
		to_date: h.to_date || h.from_date,
	}));
	frappe.call({
		method: `${NS}.recompute_working_days`,
		args: {
			holidays: holidays,
			country: frm.doc.holiday_country || "ET",
			weekly_off: frm.doc.weekly_off,
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			season_length_months: frm.doc.season_length_months || 4,
		},
		freeze: !opts.silent,
		callback(r) {
			const data = r.message;
			if (!data) return;
			if (opts.silent) render_calendar_matrix(frm, data);
			else apply_working_days(frm, data);
			if (frm.doc.wbs && frm.doc.wbs.length) {
				build_monthly_distribution(frm, { silent: true });
				if (!opts.silent) maybe_auto_schedule(frm);
			}
			if (!opts.silent) {
				frappe.show_alert({
					message: __("Working days updated: {0}", [data.total_working_days]),
					indicator: "blue",
				});
			}
		},
	});
}

function apply_working_days(frm, data) {
	frm.clear_table("no");
	(data.working_days_rows || []).forEach((row) => {
		const child = frm.add_child("no");
		child.year = row.year;
		for (let m = 1; m <= 12; m++) child[String(m)] = row[String(m)] || 0;
	});
	frm.refresh_field("no");
	render_calendar_matrix(frm, data);
	frm.dirty();
}

function render_working_days_html(frm, html) {
	const field = frm.get_field("working_days_html");
	if (field && field.$wrapper) field.$wrapper.html(html || "");
}

function render_calendar_matrix(frm, data) {
	const field = frm.get_field("working_days_html");
	if (!field || !field.$wrapper) return;
	const months = (data && data.months) || [];
	if (!months.length) {
		render_working_days_html(frm, html_placeholder(__("No months in the selected project period.")));
		return;
	}
	frm.__calendar = data;
	const t = (data && data.totals) || {};
	const esc = frappe.utils.escape_html;
	const val = (v) => flt(v) ? flt(v).toLocaleString("en-US", { maximumFractionDigits: 0 }) : "";

	const yearGroups = [];
	const seasonGroups = [];
	months.forEach((m) => {
		const ly = yearGroups[yearGroups.length - 1];
		if (ly && ly.year === m.year) ly.count++;
		else yearGroups.push({ year: m.year, count: 1 });
		const ls = seasonGroups[seasonGroups.length - 1];
		if (ls && ls.season === m.season) ls.count++;
		else seasonGroups.push({ season: m.season, count: 1 });
	});

	const yearHead = yearGroups.map((g) =>
		`<th colspan="${g.count}" style="${MPC_TH}text-align:center">${esc(String(g.year))}</th>`
	).join("");
	const seasonHead = seasonGroups.map((g) =>
		`<th colspan="${g.count}" style="${MPC_TH}text-align:center">${esc(g.season || "")}</th>`
	).join("");

	const dataRow = (label, cellFn, total, opts = {}) => {
		const cells = months.map((m) => `<td style="${MPC_TD}text-align:right">${cellFn(m)}</td>`).join("");
		return `<tr><td style="${MPC_LABEL}">${esc(label)}</td>${cells}<td style="${MPC_TOTAL}${opts.totalStyle || ""}">${total}</td></tr>`;
	};

	const rowsHtml =
		dataRow(__("Project Calendar"),
			(m) => `<span style="color:var(--text-muted,#8d99a6);white-space:nowrap">${esc(m.label)}</span>`, "") +
		dataRow(__("Calendar Days"), (m) => val(m.calendar_days), val(t.calendar_days)) +
		dataRow(__("Expected Rainy Days"), (m) => val(m.rainy_days), val(t.rainy_days)) +
		dataRow(__("Holidays"), (m) => val(m.holidays), val(t.holidays)) +
		dataRow(__("Holiday Leave Days"), (m) => val(m.holiday_leave_days), val(t.holiday_leave_days)) +
		dataRow(__("Sundays"), (m) => val(m.sundays), val(t.sundays)) +
		dataRow(__("Available (Working) Days"),
			(m) => `<b style="color:#0a7d33">${val(m.working_days)}</b>`,
			`<b style="color:#0a7d33">${val(t.working_days)}</b>`,
			{ totalStyle: "color:#0a7d33" });

	field.$wrapper.html(
		`<div style="border:1px solid ${MPC_BORDER};border-radius:8px;overflow:hidden;margin:4px 0;background:var(--fg-color,#fff)">` +
		`<div style="padding:8px 12px;background:${MPC_HEAD_BG};border-bottom:1px solid ${MPC_BORDER};font-size:12px;color:var(--text-muted,#8d99a6)">` +
		`<b>${__("Working Calendar")}</b> · ${esc(data.start_date || "")} → ${esc(data.end_date || "")} · ${__("Weekly Off")}: ${esc(data.weekly_off || "Sunday")}</div>` +
		`<div style="overflow:auto;max-height:70vh">` +
		`<table style="border-collapse:collapse;font-size:12px;width:100%">` +
		`<thead>` +
		`<tr><th style="${MPC_TH}"></th>${yearHead}<th rowspan="2" style="${MPC_TH}text-align:right;vertical-align:middle">${__("TOTAL")}</th></tr>` +
		`<tr><th style="${MPC_TH}text-align:left">${__("Season")}</th>${seasonHead}</tr>` +
		`</thead>` +
		`<tbody>${rowsHtml}</tbody>` +
		`</table></div></div>`
	);
}

function render_matrix_html(frm, html) {
	const field = frm.get_field("monthly_distribution_html");
	if (field && field.$wrapper) field.$wrapper.html(html || "");
}

function html_placeholder(text) {
	return `<div style="border:1px dashed #cbd5e1;border-radius:10px;padding:12px 14px;color:#64748b;margin:4px 0">${frappe.utils.escape_html(text)}</div>`;
}

// ---------------------------------------------------------------------------
// Monthly / seasonal workload distribution + resource distribution
// ---------------------------------------------------------------------------
function build_monthly_distribution(frm, opts = {}) {
	if (!frm.doc.start_date || !frm.doc.end_date) {
		if (!opts.silent) frappe.msgprint(__("Please set the Project Start Date and Project End Date first."));
		return;
	}
	if (!frm.doc.wbs || !frm.doc.wbs.length) {
		if (!opts.silent) frappe.msgprint(__("Please load the tasks first."));
		return;
	}

	const holidays = (frm.doc.holiday || []).map((h) => ({
		day_type: h.day_type || "Holiday",
		from_date: h.from_date,
		to_date: h.to_date || h.from_date,
	}));
	const tasks = frm.doc.wbs.filter((row) => row.task_id).map((row) => ({
		task_id: row.task_id, task_name: row.task_name, series: row.series,
		uom: row.uom, contract_qty: row.contract_qty, task_unit_rate: row.task_unit_rate,
		start_date: row.start_date || frm.doc.start_date,
		finish_date: row.finish_date || frm.doc.end_date,
	}));
	const overrides = (frm.doc.distribution || [])
		.filter((d) => d.task_id && d.month && d.qty != null && d.qty !== "")
		.map((d) => ({ task_id: d.task_id, month: d.month, qty: d.qty }));

	const machinery = [];
	const manpower = [];
	const material = [];

	mp_log("build_monthly_distribution request", {
		start_date: frm.doc.start_date,
		end_date: frm.doc.end_date,
		season_length_months: frm.doc.season_length_months || 4,
		tasks: tasks.length,
		overrides: overrides.length,
		machinery: machinery.length,
		manpower: manpower.length,
		material: material.length,
	});
	mp_log("build_monthly_distribution tasks (first 5)", tasks.slice(0, 5));
	mp_log("build_monthly_distribution overrides (first 5)", overrides.slice(0, 5));

	frappe.call({
		method: `${NS}.get_monthly_distribution`,
		args: {
			holiday_list: frm.doc.holiday_list,
			country: frm.doc.holiday_country || "ET",
			holidays,
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			tasks,
				overrides,
				season_length_months: frm.doc.season_length_months || 4,
				auto_distribute: 0,
				machinery,
				manpower,
				material,
			},
			freeze: !opts.silent,
			freeze_message: __("Loading monthly distribution..."),
		callback(r) {
			const data = r.message || {};
			mp_log("get_monthly_distribution response", data);
			mp_log("get_monthly_distribution counts", {
				columns: (data.columns || []).length,
				rows: (data.rows || []).length,
			});
			frm.__mp_distribution_data = data;
			render_cached_distribution(frm);
			if (!opts.silent) {
				frappe.show_alert({
					message: __("{0} task(s) over {1} month(s)", [
						(data.rows || []).length,
						(data.columns || []).length,
					]),
					indicator: "green",
				});
			}
		},
	});
}

function render_monthly_matrix(frm, data) {
	const field = frm.get_field("monthly_distribution_html");
	if (!field || !field.$wrapper) return;
	const cols = (data && data.columns) || [];
	const rows = (data && data.rows) || [];
	mp_log("render_monthly_matrix columns", cols);
	mp_log("render_monthly_matrix row summary", rows.map((r) => ({
		task_id: r.task_id,
		task_name: r.task_name,
		uom: r.uom,
		contract_qty: r.contract_qty,
		distributed_qty: r.distributed_qty,
		cells: r.cells,
	})));
	if (!cols.length || !rows.length) {
		mp_log("render_monthly_matrix empty", { columns: cols.length, rows: rows.length });
		render_matrix_html(frm, html_placeholder(__("Nothing to distribute yet. Load tasks and build the calendar first.")));
		return;
	}
	const groups = [];
	cols.forEach((c) => {
		const last = groups[groups.length - 1];
		if (last && last.season === c.season) last.count++;
		else groups.push({ season: c.season, count: 1 });
	});
	mp_log("render_monthly_matrix season groups", groups);
	const season_cells = groups.map((g) =>
		`<th colspan="${g.count}" style="${DIST_TH}text-align:center">${frappe.utils.escape_html(g.season || "")}</th>`
	).join("");
	const number_cells = cols.map((c) =>
		`<th style="${DIST_TH}color:#64748b;font-weight:500">${c.month_index}</th>`
	).join("");
	const month_cells = cols.map((c) =>
		`<th style="${DIST_TH}white-space:nowrap">${frappe.utils.escape_html(c.label)}</th>`
	).join("");
	const wd_total = cols.reduce((s, c) => s + flt(c.working_days), 0);
	const wd_cells = cols.map((c) =>
		`<td style="${DIST_WD}">${c.working_days == null ? "" : c.working_days}</td>`
	).join("");

	const body = rows.map((r, i) => {
		const task_id = String(r.task_id == null ? "" : r.task_id);
		const cells = cols.map((c) => {
			const cell = r.cells[c.key];
			const qty = cell ? flt(cell.qty) : 0;
			const manual = !!(cell && cell.manual);
			const pct = cell ? cell.percent : 0;
			const title = `${frappe.utils.escape_html(c.label)}: ${fmt_num(qty)} (${fmt_num(pct, 1)}%)${manual ? " • " + __("manual") : ""}`;
			return `<td title="${title}" style="${DIST_TD}padding:2px;text-align:right;${heat_style(pct)}">` +
				`<input type="number" step="any" min="0" class="mpdm-cell" data-task="${frappe.utils.escape_html(task_id)}" data-month="${frappe.utils.escape_html(c.key)}" data-prev="${qty ? qty : ""}" value="${qty ? qty : ""}" ` +
				`style="${MPDM_INPUT}${manual ? MPDM_INPUT_MANUAL : ""}"></td>`;
		}).join("");
		return `<tr class="mpdm-item" data-task="${frappe.utils.escape_html(task_id)}" data-qty="${get_view_year(frm) ? "" : flt(r.contract_qty)}">` +
			`<td style="${DIST_TD}color:#94a3b8">${frappe.utils.escape_html(r.series || r.task_id || String(i + 1))}</td>` +
			`<td style="${DIST_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${frappe.utils.escape_html(r.task_name || r.task_id || "")}">${frappe.utils.escape_html(r.task_name || r.task_id || "")}</td>` +
			`<td style="${DIST_TD}white-space:nowrap">${frappe.utils.escape_html(r.uom || "")}</td>` +
			`<td style="${DIST_TD}text-align:right;font-weight:600">${fmt_num(r.contract_qty)}</td>` +
			cells +
			`<td class="mpdm-rowtotal" style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(r.distributed_qty)}</td>` +
			"</tr>";
	}).join("");

	const col_total = {};
	cols.forEach((c) => (col_total[c.key] = 0));
	rows.forEach((r) => {
		cols.forEach((c) => {
			const cell = r.cells[c.key];
			if (cell) col_total[c.key] += flt(cell.qty);
		});
	});
	const grand_total = rows.reduce((s, r) => s + flt(r.distributed_qty), 0);
	mp_log("render_monthly_matrix totals", { col_total: col_total, grand_total: grand_total, wd_total: wd_total });
	const foot_cells = cols.map((c) =>
		`<td class="mpdm-foot" data-month="${frappe.utils.escape_html(c.key)}" style="${DIST_TF}text-align:right">${col_total[c.key] ? fmt_num(col_total[c.key], 2) : ""}</td>`
	).join("");

	field.$wrapper.html(
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
		'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
			`<b>${__("Workload Distribution")}</b> · ${rows.length} ${__("items")} · ${cols.length} ${__("months")} · ` +
			`${scope_note(frm)} · ` +
			`<span style="color:#92400e">${__("enter the monthly qty; empty months are not auto-distributed")}</span></div>` +
		'<div style="overflow:auto;max-height:75vh">' +
		'<table style="border-collapse:collapse;font-size:12px;width:100%">' +
		"<thead>" +
		`<tr><th rowspan="3" style="${DIST_TH}text-align:left">${__("Item")}</th>` +
		`<th rowspan="3" style="${DIST_TH}text-align:left">${__("Description")}</th>` +
		`<th rowspan="3" style="${DIST_TH}">${__("Unit")}</th>` +
		`<th rowspan="3" style="${DIST_TH}text-align:right">${__("Project Qty")}</th>` +
		season_cells +
		`<th rowspan="3" style="${DIST_TH}text-align:right">${__("TOTAL")}</th></tr>` +
		`<tr>${number_cells}</tr>` +
		`<tr>${month_cells}</tr>` +
		"</thead>" +
		"<tbody>" +
		`<tr><td colspan="4" style="${DIST_WD_LBL}">${__("Available working days of months")}</td>${wd_cells}<td style="${DIST_WD}font-weight:700">${wd_total}</td></tr>` +
		body +
		"</tbody>" +
		`<tfoot><tr><td colspan="4" style="${DIST_TF}font-weight:600">${__("Total")}</td>${foot_cells}<td class="mpdm-grand" style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(grand_total)}</td></tr></tfoot>` +
		"</table></div></div>"
	);
	bind_distribution_cells(frm);
}

function bind_distribution_cells(frm) {
	const field = frm.get_field("monthly_distribution_html");
	if (!field || !field.$wrapper) return;
	field.$wrapper.off("input.mpdm").on("input.mpdm", "input.mpdm-cell", function () {
		on_distribution_cell_edit(frm, this);
	});
}

function on_distribution_cell_edit(frm, input) {
	const $in = $(input);
	const task_id = String($in.attr("data-task") || "");
	const month = String($in.attr("data-month") || "");
	const raw = $in.val();
	const prev = $in.attr("data-prev") == null ? "" : $in.attr("data-prev");

	const applied = set_distribution_override(frm, task_id, month, raw);
	if (!applied) $in.val(prev);

	const value = applied ? raw : prev;
	const has_val = value !== "" && value != null && !isNaN(flt(value));
	$in.attr("style", MPDM_INPUT + (has_val ? MPDM_INPUT_MANUAL : ""));
	if (applied) $in.attr("data-prev", raw);
	refresh_row_total($in.closest("tr"));
	refresh_distribution_footer(frm);
}

function set_distribution_override(frm, task_id, month, raw) {
	frm.doc.distribution = frm.doc.distribution || [];
	const list = frm.doc.distribution;
	for (let i = list.length - 1; i >= 0; i--) {
		if (!list[i].task_id || !list[i].month) list.splice(i, 1);
	}
	const row = list.find((d) => String(d.task_id) === task_id && String(d.month) === month);
	const has_val = raw !== "" && raw != null && !isNaN(flt(raw));
	if (!has_val) {
		if (row) {
			list.splice(list.indexOf(row), 1);
			frm.dirty();
			refresh_child_grid(frm);
		}
		return true;
	}

	const contractRow = (frm.doc.wbs || []).find((r) => r.task_id === task_id);
	const contractQty = contractRow ? flt(contractRow.contract_qty) : 0;
	if (contractQty) {
		let other = 0;
		list.forEach((d) => {
			if (String(d.task_id) === task_id && String(d.month) !== month) other += flt(d.qty);
		});
		if (other + flt(raw) > contractQty + 0.000000001) {
			frappe.msgprint({
				title: __("Quantity exceeded"),
				indicator: "red",
				message: __("Task {0}: distributed qty {1} exceeds the total qty {2}.", [
					contractRow.task_name || task_id, other + flt(raw), contractQty,
				]),
			});
			return false;
		}
	}

	const target = row || frappe.model.add_child(frm.doc, "Master Plan Distribution", "distribution");
	target.task_id = task_id;
	target.month = month;
	target.qty = flt(raw);
	frm.dirty();
	refresh_child_grid(frm);
	return true;
}

function refresh_child_grid(frm) {
	const field = frm.fields_dict && frm.fields_dict.distribution;
	if (field && field.grid && field.grid.refresh) field.grid.refresh();
}

function refresh_row_total($row) {
	let sum = 0;
	$row.find("input.mpdm-cell").each(function () { sum += flt($(this).val()); });
	const raw_target = $row.attr("data-qty");
	const $cell = $row.find(".mpdm-rowtotal");
	$cell.text(fmt_num(sum, 2));
	if (raw_target === "" || raw_target == null) {
		$cell.css("color", "").removeAttr("title");
		return;
	}
	const target = flt(raw_target);
	const diff = Math.round((sum - target) * 100) / 100;
	if (sum > target + 0.0001) {
		$cell.css("color", "#dc2626").attr("title", __("Total exceeds Contract Qty by {0}", [diff]));
	} else if (sum < target - 0.0001) {
		$cell.css("color", "#b91c1c").attr("title", __("Differs from Project Qty by {0}", [diff]));
	} else {
		$cell.css("color", "").removeAttr("title");
	}
}

function refresh_distribution_footer(frm) {
	const field = frm.get_field("monthly_distribution_html");
	if (!field || !field.$wrapper) return;
	const totals = {};
	let grand = 0;
	field.$wrapper.find("tr.mpdm-item").each(function () {
		$(this).find("input.mpdm-cell").each(function () {
			const m = $(this).attr("data-month");
			const v = flt($(this).val());
			totals[m] = (totals[m] || 0) + v;
			grand += v;
		});
	});
	field.$wrapper.find("td.mpdm-foot").each(function () {
		const m = $(this).attr("data-month");
		$(this).text(totals[m] ? fmt_num(totals[m], 2) : "");
	});
	field.$wrapper.find(".mpdm-grand").text(fmt_num(grand, 2));
}

// ---------------------------------------------------------------------------
// Activity sequencing + CPM schedule + Gantt
// ---------------------------------------------------------------------------
function maybe_auto_schedule(frm) {
	if (!frm.doc.project || !frm.doc.start_date || !frm.doc.end_date) return;
	if (!frm.doc.wbs || !frm.doc.wbs.length) return;
	run_schedule_engine(frm, { silent: true });
}

function ensure_sequencing(frm) {
	const rows = (frm.doc.wbs || []).filter((r) => r.task_id);
	if ((frm.doc.activity_sequencing || []).length || rows.length < 2) return;
	frm.clear_table("activity_sequencing");
	for (let i = 1; i < rows.length; i++) {
		const c = frm.add_child("activity_sequencing");
		c.activity = rows[i].task_id;
		c.predecessor_activity = rows[i - 1].task_id;
		c.relationship_type = "Finish to Start";
		c.lag_days = 0;
		c.lead_days = 0;
	}
	frm.refresh_field("activity_sequencing");
}

function run_schedule_engine(frm, opts = {}) {
	if (!frm.doc.project || !frm.doc.wbs || !frm.doc.wbs.length) {
		if (!opts.silent) frappe.msgprint(__("Load the project tasks first."));
		return;
	}
	if (!frm.doc.start_date || !frm.doc.end_date) {
		if (!opts.silent) frappe.msgprint(__("Please set the Project Start Date and Project End Date first."));
		return;
	}
	ensure_sequencing(frm);

	const tasks = (frm.doc.wbs || []).filter((r) => r.task_id).map((r) => ({
		task_id: r.task_id, task_name: r.task_name, duration: flt(r.duration),
	}));
	const sequencing = (frm.doc.activity_sequencing || []).map((r) => ({
		activity: r.activity, predecessor_activity: r.predecessor_activity,
		relationship_type: r.relationship_type, lag_days: r.lag_days, lead_days: r.lead_days,
	}));
	const holidays = (frm.doc.holiday || []).map((h) => ({
		day_type: h.day_type || "Holiday",
		from_date: h.from_date,
		to_date: h.to_date || h.from_date,
	}));

	frappe.call({
		method: `${NS}.compute_schedule`,
		args: {
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			holidays,
			tasks,
			sequencing,
			weekly_off: frm.doc.weekly_off,
			start_date_of_first_task: frm.doc.start_date_of_first_task,
			write_back: 1,
		},
		freeze: !opts.silent,
		freeze_message: __("Scheduling activities..."),
		callback(r) {
			const data = r.message;
			if (!data) return;
			apply_schedule(frm, data);
			if (!opts.silent) {
				frappe.show_alert({
					message: __("Project duration: {0} working day(s)", [data.critical_path_duration_in_day]),
					indicator: "green",
				});
			}
		},
	});
}

function apply_schedule(frm, data) {
	const by_id = {};
	(data.rows || []).forEach((r) => (by_id[r.task_id] = r));
	(frm.doc.wbs || []).forEach((row) => {
		const s = by_id[row.task_id];
		if (!s) return;
		row.start_date = s.start_date;
		row.finish_date = s.finish_date;
		row.total_float = s.total_float;
	});
	frm.refresh_field("wbs");
	render_gantt(frm, data.rows);
	frm.dirty();
	build_monthly_distribution(frm, { silent: true });  // cascades to resources
}

function render_gantt(frm, rows) {
	const field = frm.get_field("gantt_html");
	if (!field || !field.$wrapper) return;
	rows = (rows || []).filter((r) => r.start_date && r.finish_date);
	if (!rows.length) {
		field.$wrapper.html(html_placeholder(__("Click 'Run Schedule' to build the Gantt chart.")));
		return;
	}
	const esc = frappe.utils.escape_html;
	const DAY = 86400000;
	const toDate = (s) => frappe.datetime.str_to_obj(s);
	const days = (a, b) => Math.round((toDate(b) - toDate(a)) / DAY);

	let min = null, max = null;
	rows.forEach((r) => {
		const s = toDate(r.start_date);
		const e = toDate(r.finish_date);
		if (!min || s < min) min = s;
		if (!max || e > max) max = e;
	});
	const total = Math.max(1, days(min, max) + 1);
	const off = (d) => days(min, d) / total;

	const months = [];
	let cur = new Date(min.getFullYear(), min.getMonth(), 1);
	while (cur <= max) {
		const mStart = cur < min ? min : cur;
		const monthEnd = new Date(cur.getFullYear(), cur.getMonth() + 1, 0);
		const mEnd = monthEnd > max ? max : monthEnd;
		months.push({
			label: new Date(cur.getFullYear(), cur.getMonth(), 1).toLocaleString("en-US", { month: "short", year: "2-digit" }),
			left: off(mStart),
			width: (days(mStart, mEnd) + 1) / total,
		});
		cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
	}
	const monthHead = months.map((m) =>
		`<div style="position:absolute;left:${(m.left * 100).toFixed(4)}%;width:${(m.width * 100).toFixed(4)}%;border-left:1px solid #e2e8f0;box-sizing:border-box;padding:2px 4px;font-size:10px;color:#64748b;white-space:nowrap;overflow:hidden">${esc(m.label)}</div>`
	).join("");

	const body = rows.map((r) => {
		const left = off(r.start_date) * 100;
		const width = ((days(r.start_date, r.finish_date) + 1) / total) * 100;
		const color = r.is_critical ? "#dc2626" : "#2563eb";
		const label = `${r.task_name || r.task_id} (${r.start_date} → ${r.finish_date})`;
		return `<tr><td style="padding:2px 6px;border:1px solid #eef2f7;font-size:11px;max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(label)}">${esc(r.task_name || r.task_id)}</td>` +
			`<td style="padding:0;border:1px solid #eef2f7;position:relative;height:22px">` +
			`<div title="${esc(label)}" style="position:absolute;top:3px;height:16px;left:${left.toFixed(4)}%;width:${width.toFixed(4)}%;background:${color};border-radius:3px"></div></td></tr>`;
	}).join("");

	field.$wrapper.html(
		`<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">` +
		`<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">` +
		`<b>${__("Gantt Chart")}</b> · <span style="color:#dc2626">■</span> ${__("Critical")} · <span style="color:#2563eb">■</span> ${__("Non-critical")}</div>` +
		`<div style="overflow:auto;max-height:70vh"><table style="border-collapse:collapse;font-size:11px;width:100%">` +
		`<thead><tr><th style="padding:5px 8px;border:1px solid #e2e8f0;background:#f1f5f9;text-align:left;width:280px">${__("Activity")}</th>` +
		`<th style="padding:0;border:1px solid #e2e8f0;background:#f1f5f9;position:relative;height:22px">${monthHead}</th></tr></thead>` +
		`<tbody>${body}</tbody></table></div></div>`
	);
}

function render_gantt_from_wbs(frm) {
	if (!frm.doc.wbs || !frm.doc.wbs.length) return;
	const rows = frm.doc.wbs.filter((r) => r.task_id && r.start_date && r.finish_date).map((r) => ({
		task_id: r.task_id, task_name: r.task_name, start_date: r.start_date,
		finish_date: r.finish_date, is_critical: flt(r.total_float) <= 0,
	}));
	if (rows.length) render_gantt(frm, rows);
}

// ---------------------------------------------------------------------------
// Style constants
// ---------------------------------------------------------------------------
const DIST_TH =
	"padding:5px 6px;border:1px solid #e2e8f0;background:#f1f5f9;font-weight:600;white-space:nowrap;";
const DIST_TD = "padding:4px 6px;border:1px solid #eef2f7;white-space:nowrap;";
const DIST_TF = "padding:5px 6px;border:1px solid #e2e8f0;background:#f8fafc;white-space:nowrap;";
const DIST_WD =
	"padding:5px 6px;border:1px solid #e2e8f0;background:#fffbeb;color:#92400e;font-weight:600;text-align:right;";
const DIST_WD_LBL =
	"padding:5px 8px;border:1px solid #e2e8f0;background:#fffbeb;color:#92400e;font-weight:600;white-space:nowrap;";
const MPDM_INPUT =
	"width:66px;border:none;background:transparent;text-align:right;font:inherit;color:inherit;padding:2px 3px;border-radius:4px;";
const MPDM_INPUT_MANUAL =
	"box-shadow:inset 0 0 0 2px #f59e0b;background:rgba(255,255,255,.55);";

const MPC_BORDER = "var(--border-color,#d1d8dd)";
const MPC_HEAD_BG = "var(--subtle-fg,#f4f5f6)";
const MPC_TH = `padding:6px 8px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);`;
const MPC_LABEL = `padding:6px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);white-space:nowrap;text-align:left;`;
const MPC_TD = `padding:5px 8px;border:1px solid ${MPC_BORDER};color:var(--text-color,#1f272e);`;
const MPC_TOTAL = `padding:5px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:700;text-align:right;`;

function heat_style(pct) {
	const p = Math.max(0, Math.min(100, flt(pct)));
	const alpha = (0.05 + (p / 100) * 0.6).toFixed(3);
	const color = p > 55 ? "#ffffff" : "#1f2937";
	return `background:rgba(37,99,235,${alpha});color:${color};`;
}

function fmt_num(value, dp) {
	dp = dp == null ? 2 : dp;
	const n = flt(value);
	if (!n) return "";
	return n.toLocaleString("en-US", { maximumFractionDigits: dp });
}

const RP_TABS = [
	{ key: "doz", field: "resource_doz_html", title: "Dozer Requirement", kind: "machine" },
	{ key: "exc", field: "resource_exc_html", title: "Excavator Requirement", kind: "machine" },
	{ key: "grader", field: "resource_grader_html", title: "Grader Requirement", kind: "machine" },
	{ key: "loader", field: "resource_loader_html", title: "Loader Requirement", kind: "machine" },
	{ key: "dt", field: "resource_dt_html", title: "Dump Truck Requirement", kind: "dt" },
	{ key: "equipment", field: "resource_equipment_html", title: "Equipment Requirement", kind: "equipment" },
	{ key: "crew", field: "resource_crew_html", title: "Crew Formation", kind: "crew" },
	{ key: "fuel", field: "resource_fuel_html", title: "Fuel Requirement", kind: "fuel" },
	{ key: "manpower", field: "resource_manpower_html", title: "Manpower schedule", kind: "manpower" },
	{ key: "material", field: "resource_material_html", title: "Material Schedule", kind: "material" },
];

const RP_MACHINE_DEFAULTS = {
	doz: 0.1,
	exc: 20,
	grader: 80,
	loader: 140,
	dt: 15,
};

const RP_TH = "padding:7px 8px;border:1px solid #dbe4ef;background:#f1f5f9;font-weight:700;white-space:nowrap;color:#0f172a;";
const RP_TD = "padding:6px 8px;border:1px solid #e8eef5;white-space:nowrap;color:#1e293b;";
const RP_ROW = "padding:6px 8px;border:1px solid #dbe4ef;background:#f8fafc;font-weight:700;color:#0f172a;white-space:nowrap;";
const RP_WORKLOAD = "padding:6px 8px;border:1px solid #e8eef5;white-space:nowrap;color:#64748b;font-size:11px;";
const RP_INPUT = "width:78px;border:1px solid #cbd5e1;border-radius:5px;padding:3px 5px;text-align:right;font:inherit;background:#fff;";
const RP_INPUT_WIDE = "width:150px;border:1px solid #cbd5e1;border-radius:5px;padding:3px 5px;font:inherit;background:#fff;";
const RP_SELECT = "max-width:180px;border:1px solid #cbd5e1;border-radius:5px;padding:3px 5px;font:inherit;background:#fff;";
const RP_BTN = "border:1px solid #cbd5e1;background:#fff;border-radius:5px;padding:4px 9px;cursor:pointer;font-size:11px;color:#0f172a;";
const RP_BTN_PRIMARY = "border:1px solid #2563eb;background:#2563eb;color:#fff;border-radius:5px;padding:4px 10px;cursor:pointer;font-size:11px;";
const RP_BTN_DANGER = "border:1px solid #fecaca;background:#fff1f2;color:#b91c1c;border-radius:5px;padding:3px 7px;cursor:pointer;font-size:11px;";
const RP_LABEL = "padding:6px 10px;border:1px solid #dbe4ef;background:#f8fafc;font-weight:700;white-space:nowrap;color:#0f172a;";

function rp_esc(value) {
	return frappe.utils.escape_html(String(value == null ? "" : value));
}

function rp_fmt(value, dp) {
	const n = Number(value || 0);
	if (!isFinite(n)) return "";
	if (Math.abs(n) < 0.0000001) return "";
	return n.toLocaleString("en-US", { maximumFractionDigits: dp == null ? 2 : dp });
}

function rp_fmt_zero(value, dp) {
	return rp_fmt(value, dp) || "0";
}

function rp_uid(prefix) {
	return `${prefix}_${Date.now().toString(36)}_${Math.floor(Math.random() * 1000)}`;
}

function rp_get_state(frm) {
	if (!frm.__mp_resource_state) {
		let raw = frm.doc.resource_plan_data;
		let saved = {};
		if (raw) {
			try {
				saved = typeof raw === "string" ? JSON.parse(raw) : raw;
			} catch (error) {
				saved = {};
			}
		}
		saved.meta = saved.meta || {};
		RP_TABS.forEach((cfg) => {
			if (!saved[cfg.key] || !Array.isArray(saved[cfg.key].rows)) saved[cfg.key] = { rows: [] };
		});
		frm.__mp_resource_state = saved;
	}
	return frm.__mp_resource_state;
}

function rp_set_state(frm, state) {
	frm.__mp_resource_state = state;
	frm.set_value("resource_plan_data", JSON.stringify(state));
	frm.dirty();
	rp_schedule_persist(frm);
}

function rp_schedule_persist(frm, delay = 900) {
	if (!frm.doc.name || frm.is_new()) return;
	clearTimeout(frm.__mp_resource_persist_timer);
	if (frm.__mp_resource_persist_inflight || frappe.ui.form.is_saving) {
		frm.__mp_resource_persist_queued = true;
		return;
	}
	frm.__mp_resource_persist_timer = setTimeout(() => rp_persist_resource_state(frm), delay);
}

function rp_persist_resource_state(frm) {
	if (!frm.doc.name || frm.is_new()) return;
	if (frm.__mp_resource_persist_inflight || frappe.ui.form.is_saving) {
		frm.__mp_resource_persist_queued = true;
		return;
	}
	frm.__mp_resource_persist_queued = false;
	frm.__mp_resource_persist_inflight = true;
	frappe.call({
		method: `${NS}.save_resource_plan_state`,
		args: {
			name: frm.doc.name,
			state: JSON.stringify(rp_get_state(frm)),
		},
		silent: true,
		error(r) {
			console.error("Master Plan: save_resource_plan_state failed", r);
		},
		always() {
			frm.__mp_resource_persist_inflight = false;
			if (frm.__mp_resource_persist_queued) rp_schedule_persist(frm, 100);
		},
	});
}

function rp_state_empty(state) {
	return RP_TABS.every((cfg) => !(((state || {})[cfg.key] || {}).rows || []).length);
}

function rp_reset_state(frm) {
	frm.__mp_resource_state = null;
	frm.__mp_resource_computed = null;
	frm.__mp_machine_tables_hydrated = false;
	clearTimeout(frm.__mp_resource_timer);
	clearTimeout(frm.__mp_machine_sync_timer);
	clearTimeout(frm.__mp_resource_persist_timer);
	frm.__mp_resource_persist_queued = false;
	RP_MACHINE_KEYS.forEach((tab) => {
		const field = RP_MACHINE_TABLE_FIELDS[tab];
		if (frm.get_field(field)) {
			frm.clear_table(field);
			frm.refresh_field(field);
		}
	});
	if (frm.get_field("resource_plan_data")) frm.set_value("resource_plan_data", "");
	rp_schedule_persist(frm);
}

function rp_child_from_machine_row(tab, row) {
	const out = {
		row_id: row.id || "",
		task_id: row.task_id || "",
		task_name: row.task_name || "",
		uom: row.uom || "",
		total_qty: flt(row.total_qty),
		eng_pct: flt(row.eng_pct),
		hours_day: flt(row.hours_day),
		hourly_output: flt(row.hourly_output),
		source: row.source || "manual",
	};
	if (tab === "dt") {
		RP_DT_FIELDS.forEach((field) => (out[field] = flt(row[field])));
	}
	return out;
}

function rp_machine_from_child_row(tab, row) {
	const out = {
		id: row.row_id || row.name || rp_uid(tab),
		task_id: row.task_id || "",
		task_name: row.task_name || "",
		uom: row.uom || "",
		total_qty: flt(row.total_qty),
		eng_pct: flt(row.eng_pct),
		hours_day: flt(row.hours_day),
		hourly_output: flt(row.hourly_output),
		source: row.source || "manual",
	};
	if (tab === "dt") {
		RP_DT_FIELDS.forEach((field) => (out[field] = flt(row[field])));
	}
	return out;
}

function rp_fill_empty_machine_tables(frm) {
	const state = rp_get_state(frm);
	frm.__mp_syncing_machine = true;
	RP_MACHINE_KEYS.forEach((tab) => {
		const field = RP_MACHINE_TABLE_FIELDS[tab];
		if (!frm.get_field(field) || (frm.doc[field] || []).length) return;
		const rows = (state[tab] || {}).rows || [];
		if (!rows.length) return;
		frm.clear_table(field);
		rows.forEach((row) => frm.add_child(field, rp_child_from_machine_row(tab, row)));
		frm.refresh_field(field);
	});
	frm.__mp_syncing_machine = false;
	frm.__mp_machine_tables_hydrated = true;
}

function rp_replace_machine_table(frm, tab) {
	const field = RP_MACHINE_TABLE_FIELDS[tab];
	if (!field || !frm.get_field(field)) return;
	const rows = ((rp_get_state(frm)[tab] || {}).rows) || [];
	frm.__mp_syncing_machine = true;
	frm.clear_table(field);
	rows.forEach((row) => frm.add_child(field, rp_child_from_machine_row(tab, row)));
	frm.refresh_field(field);
	frm.__mp_syncing_machine = false;
	frm.__mp_machine_tables_hydrated = true;
}

function rp_sync_machine_tables(frm, opts = {}) {
	if (frm.__mp_syncing_machine) return;
	const state = rp_get_state(frm);
	const before = JSON.stringify(state);
	frm.__mp_syncing_machine = true;
	try {
		RP_MACHINE_KEYS.forEach((tab) => {
			const field = RP_MACHINE_TABLE_FIELDS[tab];
			if (!frm.get_field(field)) return;
			const child_rows = frm.doc[field] || [];
			if (child_rows.length || frm.__mp_machine_tables_hydrated) {
				state[tab] = { rows: child_rows.map((row) => rp_machine_from_child_row(tab, row)) };
			} else {
				const rows = (state[tab] || {}).rows || [];
				if (rows.length) {
					frm.clear_table(field);
					rows.forEach((row) => frm.add_child(field, rp_child_from_machine_row(tab, row)));
					frm.refresh_field(field);
				}
			}
		});
		frm.__mp_machine_tables_hydrated = true;
		if (JSON.stringify(state) !== before) rp_set_state(frm, state);
	} finally {
		frm.__mp_syncing_machine = false;
	}
	if (!opts.skip_compute) rp_compute_resource_plan(frm, { skip_seed: true });
}

function rp_schedule_machine_sync(frm) {
	clearTimeout(frm.__mp_machine_sync_timer);
	frm.__mp_machine_sync_timer = setTimeout(() => rp_sync_machine_tables(frm), 350);
}

function rp_options(items, selected, placeholder) {
	const list = Array.isArray(items) ? items : [];
	let html = `<option value="">${rp_esc(placeholder || __("Select..."))}</option>`;
	list.forEach((item) => {
		const value = item.value == null ? "" : String(item.value);
		const label = item.label == null ? value : String(item.label);
		const is_selected = String(selected == null ? "" : selected) === value ? " selected" : "";
		html += `<option value="${rp_esc(value)}"${is_selected}>${rp_esc(label)}</option>`;
	});
	return html;
}

function rp_task_options(data, selected) {
	return rp_options(
		(data.rows || []).map((r) => ({
			value: r.task_id,
			label: `${r.series ? r.series + " · " : ""}${r.task_name || r.task_id}`,
		})),
		selected,
		__("Select task")
	);
}

function rp_equipment_options(computed, selected) {
	const rows = ((computed || {}).tabs || {}).equipment?.rows || [];
	return rp_options(rows.map((r) => ({ value: r.id, label: r.name || r.id })), selected, __("Select equipment"));
}

function rp_machine_option_groups(computed) {
	const groups = [];
	RP_MACHINE_KEYS.forEach((tab) => {
		const rows = ((computed || {}).tabs || {})[tab]?.rows || [];
		rows.forEach((row) => groups.push({
			value: `${tab}:${row.id}`,
			label: `${tab.toUpperCase()} · ${row.task_name || row.id}`,
		}));
	});
	return groups;
}

function rp_machine_tab_options(selected) {
	return rp_options(
		RP_MACHINE_KEYS.map((key) => ({ value: key, label: key.toUpperCase() })),
		selected,
		__("Select machine tab")
	);
}

function rp_input(tab, index, field, value, opts = {}) {
	const type = opts.type || "text";
	const step = type === "number" ? ` step="${opts.step || "any"}"` : "";
	const style = opts.wide ? RP_INPUT_WIDE : RP_INPUT;
	return `<input type="${type}"${step} class="mpr-input" data-tab="${rp_esc(tab)}" data-row="${index}" data-field="${rp_esc(field)}" data-type="${type}" value="${rp_esc(value == null ? "" : value)}" style="${style}" placeholder="${rp_esc(opts.placeholder || "")}">`;
}

function rp_select(tab, index, field, value, options, opts = {}) {
	return `<select class="mpr-input" data-tab="${rp_esc(tab)}" data-row="${index}" data-field="${rp_esc(field)}" style="${opts.wide ? RP_INPUT_WIDE : RP_SELECT}">${options}</select>`;
}

function rp_btn(action, label, tab, index, opts = {}) {
	return `<button type="button" class="mpr-action" data-action="${rp_esc(action)}" data-tab="${rp_esc(tab)}" data-row="${index == null ? "" : index}" style="${opts.primary ? RP_BTN_PRIMARY : (opts.danger ? RP_BTN_DANGER : RP_BTN)}">${rp_esc(label)}</button>`;
}

function rp_month_input(tab, index, month, value, display) {
	return `<div title="${__("Manual monthly value")}">` +
		`<div style="font-size:10px;color:#64748b;margin-bottom:2px">${rp_fmt(display)}</div>` +
		`<input type="number" step="any" class="mpr-input" data-tab="${rp_esc(tab)}" data-row="${index}" data-field="manual_cells" data-month="${rp_esc(month)}" data-type="number" value="${rp_esc(value == null ? "" : value)}" style="width:70px;border:1px dashed #f59e0b;border-radius:5px;padding:2px 4px;text-align:right;font:inherit;background:#fffbeb">` +
		"</div>";
}

function rp_manual_cell(state, tab, index, month, fallback) {
	const row = ((state[tab] || {}).rows || [])[index] || {};
	const saved = (row.manual_cells || {})[month];
	return saved == null ? (fallback == null ? "" : fallback) : saved;
}

function rp_card(title, subtitle, toolbar, body) {
	return `<div style="border:1px solid #dbe4ef;border-radius:10px;overflow:hidden;background:#fff;margin:6px 0">` +
		`<div style="padding:9px 12px;background:#f8fafc;border-bottom:1px solid #dbe4ef;display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap">` +
		`<div style="font-size:12px"><b>${rp_esc(title)}</b>${subtitle ? ` · <span style="color:#64748b">${rp_esc(subtitle)}</span>` : ""}</div>` +
		`<div style="display:flex;gap:6px;flex-wrap:wrap">${toolbar || ""}</div></div>` +
		`<div style="overflow:auto;max-height:72vh">${body}</div></div>`;
}

function rp_month_head(data, left_headers, right_headers = []) {
	const cols = data.columns || [];
	let head = "<thead><tr>";
	left_headers.forEach((h) => (head += `<th rowspan="2" style="${RP_TH}text-align:left">${h}</th>`));
	cols.forEach((c) => (head += `<th style="${RP_TH}text-align:center;min-width:92px">${rp_esc(c.label || c.key)}</th>`));
	right_headers.forEach((h) => (head += `<th rowspan="2" style="${RP_TH}text-align:right">${h}</th>`));
	head += "</tr><tr>";
	cols.forEach((c) => (head += `<td style="${RP_WORKLOAD}text-align:center;font-weight:700;color:#92400e">${rp_esc(c.working_days == null ? "" : c.working_days)}</td>`));
	head += "</tr></thead>";
	return head;
}

function rp_toolbar(tab, show_seed = true) {
	let html = "";
	if (show_seed) html += rp_btn("seed-tab", __("Reload from CBD"), tab, null);
	if (!RP_MACHINE_KEYS.includes(tab)) {
		html += rp_btn("add-row", __("Add Row"), tab, null, { primary: true });
	}
	html += rp_btn("recalc", __("Recalculate"), tab, null);
	return html;
}

function rp_clear_tabs(frm, message) {
	RP_TABS.forEach((cfg) => {
		const field = frm.get_field(cfg.field);
		if (field && field.$wrapper) field.$wrapper.html(html_placeholder(message));
	});
}

function rp_render_machine(frm, cfg, computed, state) {
	const tab = computed.tabs[cfg.key] || { rows: [], totals: {} };
	const cols = computed.columns || [];
	const is_dt = cfg.kind === "dt";
	const left = ["#", __("Task"), __("Description"), __("Project Qty")];
	if (is_dt) {
		left.push(__("Workload Qty (Eng%)"), __("Distance km"), __("Speed"), __("Load/Unload min"), __("Capacity m3"), __("Eff."), __("Avail."), __("Loose"), __("Hr/day"), __("Effective/day"));
	} else {
		left.push(__("Eng %"), __("Workload Qty (Eng%)"), __("Hr/day"), __("Hourly output"), __("Daily output"));
	}
	left.push(__("Source"));

	if (!tab.rows.length) {
		const field = frm.get_field(cfg.field);
		if (field && field.$wrapper) {
			field.$wrapper.html(rp_card(
				cfg.title,
				__("Auto-loaded from Cost Break Down machinery"),
				rp_toolbar(cfg.key),
				html_placeholder(__("No matching machinery rows found. Add a task in the task list below or reload from CBD."))
			));
			rp_bind_resource_tabs(frm);
		}
		return;
	}

	const body = tab.rows.map((row, index) => {
		const cells = cols.map((col) => {
			const cell = row.cells[col.key] || {};
			return `<td style="${RP_TD}text-align:right;min-width:92px">` +
				`<div style="font-weight:700;color:#0f172a">${rp_fmt_zero(cell.machines)}</div>` +
				`<div style="font-size:10px;color:#64748b" title="${__("Monthly workload")}">${rp_fmt_zero(cell.workload)}</div></td>`;
		}).join("");
		const daily = cols.length ? (row.cells[cols[0].key] || {}).daily_output : 0;
		const values = is_dt
			? [
				rp_fmt(row.total_workload),
				rp_fmt(row.distance),
				rp_fmt(row.speed),
				rp_fmt(row.load_unload_min),
				rp_fmt(row.capacity),
				rp_fmt(row.efficiency),
				rp_fmt(row.availability),
				rp_fmt(row.loose_factor),
				rp_fmt(row.hours_day),
				rp_fmt(daily),
			]
			: [
				rp_fmt(row.eng_pct),
				rp_fmt(row.total_workload),
				rp_fmt(row.hours_day),
				rp_fmt(row.hourly_output),
				rp_fmt(daily),
			];
		return "<tr>" +
			`<td style="${RP_TD}color:#94a3b8">${index + 1}</td>` +
			`<td style="${RP_TD}">${rp_esc(row.task_id || "")}</td>` +
			`<td style="${RP_TD}max-width:240px;overflow:hidden;text-overflow:ellipsis" title="${rp_esc(row.task_name)}">${rp_esc(row.task_name || "")}</td>` +
			`<td style="${RP_TD}text-align:right;font-weight:600">${rp_fmt(row.total_qty)}</td>` +
			values.map((value) => `<td style="${RP_TD}text-align:right;font-weight:600;color:#0f172a">${value}</td>`).join("") +
			`<td style="${RP_TD}"><span style="font-size:10px;color:#64748b">${rp_esc(row.source || "manual")}</span></td>` +
			cells +
			`<td style="${RP_ROW}text-align:right">${rp_fmt_zero(row.total)}</td>` +
			"</tr>";
	}).join("");

	const total_cells = cols.map((col) => {
		const totals = tab.totals[col.key] || {};
		const total = totals.rounded || 0;
		const exact = totals.raw || 0;
		return `<td style="${RP_ROW}text-align:right" title="${__("Exact sum")}: ${rp_fmt_zero(exact)}">${rp_fmt_zero(total, 0)}</td>`;
	}).join("");
	const grand_total = Object.values(tab.totals || {}).reduce((s, t) => s + flt(t.rounded), 0);
	const table = `<table style="border-collapse:collapse;font-size:12px;width:100%;min-width:${1100 + cols.length * 96}px">` +
		rp_month_head(computed, left, [__("Row Total")]) +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="${left.length}" style="${RP_ROW}">${__("Machinery Qty Sum")}</td>${total_cells}<td style="${RP_ROW}text-align:right">${rp_fmt_zero(grand_total, 0)}</td></tr></tfoot>` +
		"</table>";

	const subtitle = is_dt
		? __("Computed view. Workload = project qty × Eng%; edit the DT task list below. Effective m3/hr = capacity ÷ ((distance ÷ speed) + loading minutes ÷ 60) × efficiency × availability")
		: __("Computed view. Workload = project qty × Eng%; edit the task list below. Machines = workload ÷ (hourly output × hr/day × working days)");
	const field = frm.get_field(cfg.field);
	if (field && field.$wrapper) field.$wrapper.html(rp_card(cfg.title, subtitle, rp_toolbar(cfg.key), table));
}

function rp_render_equipment(frm, cfg, computed, state) {
	const rows = computed.tabs.equipment.rows || [];
	const cols = computed.columns || [];
	const left = ["#", __("Equipment"), __("Source type"), __("Source tab"), __("Source row / equipment"), __("Multiplier")];
	const machine_options = rp_machine_option_groups(computed);

	const body = rows.map((row, index) => {
		const source_type = row.source_type || "manual";
		let source_tab = rp_select(cfg.key, index, "source_tab", row.source_tab, rp_machine_tab_options(row.source_tab));
		let source_row = rp_input(cfg.key, index, "source_value", row.source_row_id || row.source_id || (Array.isArray(row.source_ids) ? row.source_ids.join(", ") : row.source_ids || ""), { wide: true });
		if (source_type === "tab_total") source_row = "";
		if (source_type === "tab_row") source_row = rp_select(cfg.key, index, "source_row_id", row.source_row_id, rp_options(machine_options, row.source_row_id, __("Select activity")));
		if (source_type === "equipment") source_row = rp_select(cfg.key, index, "source_id", row.source_id, rp_equipment_options(computed, row.source_id));
		const cells = cols.map((col) => {
			const value = (row.cells[col.key] || {}).value || 0;
			if (source_type === "manual") {
				const manual_value = rp_manual_cell(state, cfg.key, index, col.key, value);
				return `<td style="${RP_TD}text-align:right;min-width:92px">${rp_month_input(cfg.key, index, col.key, manual_value, value)}</td>`;
			}
			return `<td style="${RP_TD}text-align:right;min-width:92px;font-weight:600;color:#0f172a">${rp_fmt(value)}</td>`;
		}).join("");
		return "<tr>" +
			`<td style="${RP_TD}color:#94a3b8">${index + 1}<br>${rp_btn("remove-row", "×", cfg.key, index, { danger: true })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "name", row.name, { wide: true })}</td>` +
			`<td style="${RP_TD}">${rp_select(cfg.key, index, "source_type", source_type, rp_options([
				{ value: "tab_total", label: __("Machine tab total") },
				{ value: "tab_row", label: __("Machine activity") },
				{ value: "equipment", label: __("Equipment row") },
				{ value: "equipment_sum", label: __("Equipment sum") },
				{ value: "manual", label: __("Manual") },
			], source_type))}</td>` +
			`<td style="${RP_TD}">${source_tab}</td>` +
			`<td style="${RP_TD}">${source_row}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "multiplier", row.multiplier, { type: "number", step: "0.01" })}</td>` +
			cells +
			`<td style="${RP_ROW}text-align:right">${rp_fmt(row.peak)}</td>` +
			"</tr>";
	}).join("");

	const totals = cols.map((col) => `<td style="${RP_ROW}text-align:right">${rp_fmt((computed.tabs.equipment.totals || {})[col.key])}</td>`).join("");
	const table = `<table style="border-collapse:collapse;font-size:12px;width:100%;min-width:${900 + cols.length * 96}px">` +
		rp_month_head(computed, left, [__("Peak")]) +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="${left.length}" style="${RP_ROW}">${__("Fleet total")}</td>${totals}<td style="${RP_ROW}"></td></tr></tfoot>` +
		"</table>";
	const field = frm.get_field(cfg.field);
	if (field && field.$wrapper) field.$wrapper.html(rp_card(cfg.title, __("Peak = MAX of the monthly row; this sheet is not a grand total."), rp_toolbar(cfg.key, false), table));
}

function rp_render_crew(frm, cfg, computed) {
	const rows = computed.tabs.crew.rows || [];
	const cols = computed.columns || [];
	const left = ["#", __("Activity"), __("Source"), __("Source tab"), __("Hourly output"), __("Hr/day"), __("Crew size"), __("Daily output")];
	const body = rows.map((row, index) => {
		const cells = cols.map((col) => `<td style="${RP_TD}text-align:right;min-width:92px">${rp_fmt((row.cells[col.key] || {}).output)}</td>`).join("");
		return "<tr>" +
			`<td style="${RP_TD}color:#94a3b8">${index + 1}<br>${rp_btn("remove-row", "×", cfg.key, index, { danger: true })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "activity", row.activity, { wide: true })}</td>` +
			`<td style="${RP_TD}">${rp_select(cfg.key, index, "source_type", row.source_type, rp_options([
				{ value: "machine_tab", label: __("Machine tab output") },
				{ value: "manual", label: __("Manual") },
			], row.source_type))}</td>` +
			`<td style="${RP_TD}">${rp_select(cfg.key, index, "source_tab", row.source_tab, rp_machine_tab_options(row.source_tab))}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "hourly_output", row.hourly_output, { type: "number", step: "0.0001" })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "hours_day", row.hours_day, { type: "number" })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "crew_size", row.crew_size, { type: "number" })}</td>` +
			`<td style="${RP_ROW}text-align:right">${rp_fmt(row.daily_output)}</td>` +
			cells + "</tr>";
	}).join("");
	const table = `<table style="border-collapse:collapse;font-size:12px;width:100%;min-width:${950 + cols.length * 96}px">` +
		rp_month_head(computed, left) + `<tbody>${body}</tbody></table>`;
	const field = frm.get_field(cfg.field);
	if (field && field.$wrapper) field.$wrapper.html(rp_card(cfg.title, __("Reference only; Crew Formation does not feed fuel, manpower or materials."), rp_toolbar(cfg.key, false), table));
}

function rp_render_fuel(frm, cfg, computed, state) {
	const rows = computed.tabs.fuel.rows || [];
	const cols = computed.columns || [];
	const summary = computed.tabs.fuel.summary || {};
	const cards = `<div style="display:flex;gap:10px;flex-wrap:wrap;padding:10px 12px;border-bottom:1px solid #dbe4ef;background:#fffbeb">` +
		`<div style="font-size:11px;color:#64748b">${__("Total litres")}: <b style="color:#92400e">${rp_fmt(summary.total_litres)}</b></div>` +
		`<div style="font-size:11px;color:#64748b">${__("13,000 L tankers")}: <b style="color:#92400e">${rp_fmt(summary.tanker_loads)}</b></div>` +
		`<div style="font-size:11px;color:#64748b">${__("Scenario")} ${rp_input("fuel", -1, "scenario_pct", state.fuel.scenario_pct == null ? 85 : state.fuel.scenario_pct, { type: "number" })} % = <b style="color:#92400e">${rp_fmt(summary.scenario_litres)}</b> L</div>` +
		"</div>";
	const left = ["#", __("Item"), __("Equipment"), __("L/hr"), __("Hr/day")];
	const body = rows.map((row, index) => {
		const cells = cols.map((col) => `<td style="${RP_TD}text-align:right;min-width:92px;font-weight:600">${rp_fmt((row.cells[col.key] || {}).litres)}</td>`).join("");
		return "<tr>" +
			`<td style="${RP_TD}color:#94a3b8">${index + 1}<br>${rp_btn("remove-row", "×", cfg.key, index, { danger: true })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "item", row.item, { wide: true })}</td>` +
			`<td style="${RP_TD}">${rp_select(cfg.key, index, "equipment_id", row.equipment_id, rp_equipment_options(computed, row.equipment_id))}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "l_per_hour", row.l_per_hour, { type: "number", step: "0.01" })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "hours_day", row.hours_day, { type: "number" })}</td>` +
			cells +
			`<td style="${RP_ROW}text-align:right">${rp_fmt(row.total)}</td>` +
			"</tr>";
	}).join("");
	const totals = cols.map((col) => `<td style="${RP_ROW}text-align:right">${rp_fmt((computed.tabs.fuel.totals || {})[col.key])}</td>`).join("");
	const table = cards + `<table style="border-collapse:collapse;font-size:12px;width:100%;min-width:${750 + cols.length * 96}px">` +
		rp_month_head(computed, left, [__("Total L")]) +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="${left.length}" style="${RP_ROW}">${__("Total fuel")}</td>${totals}<td style="${RP_ROW}text-align:right">${rp_fmt(summary.total_litres)}</td></tr></tfoot>` +
		"</table>";
	const field = frm.get_field(cfg.field);
	if (field && field.$wrapper) field.$wrapper.html(rp_card(cfg.title, __("Litres = equipment count × L/hr × hr/day × working days"), rp_toolbar(cfg.key, false), table));
}

function rp_render_manpower(frm, cfg, computed, state) {
	const rows = computed.tabs.manpower.rows || [];
	const cols = computed.columns || [];
	const left = ["#", __("Role"), __("Source type"), __("Equipment"), __("Factor")];
	const body = rows.map((row, index) => {
		const source_type = row.source_type || "manual";
		let source = "";
		if (source_type === "equipment") source = rp_select(cfg.key, index, "source_id", row.source_id, rp_equipment_options(computed, row.source_id));
		if (source_type === "equipment_sum") source = rp_input(cfg.key, index, "source_ids", Array.isArray(row.source_ids) ? row.source_ids.join(", ") : row.source_ids || "", { wide: true });
		const cells = cols.map((col) => {
			const value = (row.cells[col.key] || {}).headcount || 0;
			if (source_type === "manual") {
				const manual_value = rp_manual_cell(state, cfg.key, index, col.key, value);
				return `<td style="${RP_TD}text-align:right;min-width:92px">${rp_month_input(cfg.key, index, col.key, manual_value, value)}</td>`;
			}
			return `<td style="${RP_TD}text-align:right;min-width:92px;font-weight:600">${rp_fmt(value)}</td>`;
		}).join("");
		return "<tr>" +
			`<td style="${RP_TD}color:#94a3b8">${index + 1}<br>${rp_btn("remove-row", "×", cfg.key, index, { danger: true })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "role", row.role, { wide: true })}</td>` +
			`<td style="${RP_TD}">${rp_select(cfg.key, index, "source_type", source_type, rp_options([
				{ value: "equipment", label: __("Equipment row") },
				{ value: "equipment_sum", label: __("Equipment sum (IDs)") },
				{ value: "manual", label: __("Manual") },
			], source_type))}</td>` +
			`<td style="${RP_TD}">${source}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "factor", row.factor, { type: "number", step: "0.01" })}</td>` +
			cells +
			`<td style="${RP_ROW}text-align:right">${rp_fmt(row.peak)}</td>` +
			"</tr>";
	}).join("");
	const totals = cols.map((col) => `<td style="${RP_ROW}text-align:right">${rp_fmt((computed.tabs.manpower.totals || {})[col.key])}</td>`).join("");
	const table = `<table style="border-collapse:collapse;font-size:12px;width:100%;min-width:${800 + cols.length * 96}px">` +
		rp_month_head(computed, left, [__("Peak")]) +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="${left.length}" style="${RP_ROW}">${__("Total headcount")}</td>${totals}<td style="${RP_ROW}"></td></tr></tfoot>` +
		"</table>";
	const field = frm.get_field(cfg.field);
	if (field && field.$wrapper) field.$wrapper.html(rp_card(cfg.title, __("Linked rows read the Equipment Requirement; manual rows stay editable."), rp_toolbar(cfg.key, false), table));
}

function rp_render_material(frm, cfg, computed, state) {
	const rows = computed.tabs.material.rows || [];
	const cols = computed.columns || [];
	const left = ["#", __("Item"), __("Unit"), __("Source type"), __("Task"), __("Factor"), __("Divisor")];
	const body = rows.map((row, index) => {
		const source_type = row.source_type || "manual";
		let task = "";
		if (source_type === "workload") task = rp_select(cfg.key, index, "task_id", row.task_id, rp_task_options(computed, row.task_id), { wide: true });
		const cells = cols.map((col) => {
			const value = (row.cells[col.key] || {}).value || 0;
			if (source_type === "manual") {
				const manual_value = rp_manual_cell(state, cfg.key, index, col.key, value);
				return `<td style="${RP_TD}text-align:right;min-width:92px">${rp_month_input(cfg.key, index, col.key, manual_value, value)}</td>`;
			}
			return `<td style="${RP_TD}text-align:right;min-width:92px;font-weight:600">${rp_fmt(value)}</td>`;
		}).join("");
		return "<tr>" +
			`<td style="${RP_TD}color:#94a3b8">${index + 1}<br>${rp_btn("remove-row", "×", cfg.key, index, { danger: true })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "item", row.item, { wide: true })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "unit", row.unit)}</td>` +
			`<td style="${RP_TD}">${rp_select(cfg.key, index, "source_type", source_type, rp_options([
				{ value: "fuel_total", label: __("Fuel total") },
				{ value: "workload", label: __("Workload × factor") },
				{ value: "manual", label: __("Manual") },
			], source_type))}</td>` +
			`<td style="${RP_TD}">${task}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "factor", row.factor, { type: "number", step: "0.000001" })}</td>` +
			`<td style="${RP_TD}">${rp_input(cfg.key, index, "divisor", row.divisor, { type: "number", step: "any" })}</td>` +
			cells +
			`<td style="${RP_ROW}text-align:right">${rp_fmt(row.total)}</td>` +
			"</tr>";
	}).join("");
	const totals = cols.map((col) => `<td style="${RP_ROW}text-align:right">${rp_fmt((computed.tabs.material.totals || {})[col.key])}</td>`).join("");
	const table = `<table style="border-collapse:collapse;font-size:12px;width:100%;min-width:${900 + cols.length * 96}px">` +
		rp_month_head(computed, left, [__("Total")]) +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="${left.length}" style="${RP_ROW}">${__("Total material")}</td>${totals}<td style="${RP_ROW}"></td></tr></tfoot>` +
		"</table>";
	const field = frm.get_field(cfg.field);
	if (field && field.$wrapper) field.$wrapper.html(rp_card(cfg.title, __("Fuel comes from Fuel Requirement; materials come from workload × unit consumption."), rp_toolbar(cfg.key, false), table));
}

function rp_render_all(frm, computed) {
	const state = rp_get_state(frm);
	RP_TABS.forEach((cfg) => {
		if (RP_MACHINE_KEYS.includes(cfg.key)) rp_render_machine(frm, cfg, computed, state);
		else if (cfg.key === "equipment") rp_render_equipment(frm, cfg, computed, state);
		else if (cfg.key === "crew") rp_render_crew(frm, cfg, computed);
		else if (cfg.key === "fuel") rp_render_fuel(frm, cfg, computed, state);
		else if (cfg.key === "manpower") rp_render_manpower(frm, cfg, computed, state);
		else if (cfg.key === "material") rp_render_material(frm, cfg, computed, state);
	});
	rp_bind_resource_tabs(frm);
}

function rp_default_row(tab, frm) {
	if (RP_MACHINE_KEYS.includes(tab)) {
		const row = {
			id: rp_uid(tab),
			task_id: "",
			task_name: "",
			uom: "",
			total_qty: 0,
			eng_pct: 100,
			hours_day: 8,
			hourly_output: RP_MACHINE_DEFAULTS[tab] || 0,
			source: "manual",
		};
		if (tab === "dt") Object.assign(row, {
			distance: 13, speed: 20, load_unload_min: 9, capacity: 16,
			efficiency: 0.9, availability: 0.85, loose_factor: 1.25,
		});
		return row;
	}
	if (tab === "equipment") return { id: rp_uid("eq"), name: __("New Equipment"), source_type: "manual", multiplier: 1, manual_cells: {} };
	if (tab === "crew") return { id: rp_uid("crew"), activity: __("New Crew"), source_type: "manual", hourly_output: 0, hours_day: 8, crew_size: 1 };
	if (tab === "fuel") return { id: rp_uid("fuel"), item: __("New Fuel Item"), equipment_id: "", l_per_hour: 0, hours_day: 8 };
	if (tab === "manpower") return { id: rp_uid("mp"), role: __("New Role"), source_type: "manual", factor: 1, manual_cells: {} };
	return { id: rp_uid("mat"), item: __("New Material"), unit: "", source_type: "manual", factor: 1, divisor: 1, manual_cells: {} };
}

function rp_seed_resource_plan(frm, data, opts = {}) {
	if (frm.__mp_resource_seed_pending) return;
	frm.__mp_resource_seed_pending = true;
	const tasks = (frm.doc.wbs || []).filter((r) => r.task_id).map((r) => ({
		task_id: r.task_id,
		task_name: r.task_name,
		uom: r.uom,
		contract_qty: r.contract_qty,
	}));
	frappe.call({
		method: `${NS}.get_resource_plan_seed`,
		args: {
			tasks: JSON.stringify(tasks),
			distribution: JSON.stringify(data || {}),
			material_resources: "[]",
		},
		freeze: !opts.silent,
		freeze_message: __("Loading resource plans from Cost Break Down..."),
		callback(r) {
			const seeded = r.message || {};
			const state = rp_get_state(frm);
			if (opts.tab) {
				state[opts.tab] = seeded[opts.tab] || { rows: [] };
			} else {
				RP_TABS.forEach((cfg) => (state[cfg.key] = seeded[cfg.key] || { rows: [] }));
			}
			state.meta = Object.assign({}, state.meta, { seeded: 1 });
			rp_set_state(frm, state);
			if (opts.tab && RP_MACHINE_TABLE_FIELDS[opts.tab]) rp_replace_machine_table(frm, opts.tab);
			else rp_fill_empty_machine_tables(frm);
			rp_compute_resource_plan(frm, { skip_seed: true, silent: opts.silent });
			if (!opts.silent) frappe.show_alert({ message: __("Resource rows loaded from the Cost Break Down."), indicator: "green" });
		},
		error(r) {
			console.error("Master Plan: get_resource_plan_seed failed", r);
			rp_clear_tabs(frm, __("Resource seeding failed. Check the browser console and Error Log."));
		},
		always() {
			frm.__mp_resource_seed_pending = false;
		},
	});
}

function rp_compute_resource_plan(frm, opts = {}) {
	const data = frm.__mp_distribution_data;
	if (!data || !data.columns || !data.columns.length) {
		rp_clear_tabs(frm, __("Build the workload distribution first."));
		return;
	}
	if (!opts.skip_seed) rp_sync_machine_tables(frm, { skip_compute: true });
	const state = rp_get_state(frm);
	if (!opts.skip_seed && (!state.meta.seeded || rp_state_empty(state))) {
		rp_seed_resource_plan(frm, data, { silent: true });
		return;
	}
	frappe.call({
		method: `${NS}.compute_resource_plan`,
		args: {
			distribution: JSON.stringify(data),
			state: JSON.stringify(state),
		},
		freeze: false,
		callback(r) {
			frm.__mp_resource_computed = r.message || {};
			rp_render_all(frm, frm.__mp_resource_computed);
		},
		error(r) {
			console.error("Master Plan: compute_resource_plan failed", r);
			rp_clear_tabs(frm, __("Resource calculation failed. Check the browser console and Error Log."));
		},
	});
}

function rp_schedule_compute(frm) {
	clearTimeout(frm.__mp_resource_timer);
	frm.__mp_resource_timer = setTimeout(() => rp_compute_resource_plan(frm), 450);
}

function render_resource_plan(frm, data) {
	if (!frm.doc.project || !data || !data.columns || !data.columns.length) {
		rp_clear_tabs(frm, __("Select a project and build the workload distribution first."));
		return;
	}
	rp_compute_resource_plan(frm);
}

function rp_on_input(frm, el) {
	const tab = el.getAttribute("data-tab");
	const row_index = Number(el.getAttribute("data-row"));
	const field = el.getAttribute("data-field");
	const month = el.getAttribute("data-month");
	const state = rp_get_state(frm);
	let value = el.value;
	if (el.getAttribute("data-type") === "number") value = value === "" ? 0 : Number(value);
	if (field === "source_ids") value = String(value || "").split(",").map((v) => v.trim()).filter(Boolean);

	if (row_index === -1) {
		state[tab] = state[tab] || {};
		state[tab][field] = value;
	} else {
		const row = ((state[tab] || {}).rows || [])[row_index];
		if (!row) return;
		if (month) {
			row.manual_cells = row.manual_cells || {};
			row.manual_cells[month] = value;
		} else {
			row[field] = value;
		}
		if (field === "task_id") {
			const task = ((frm.__mp_distribution_data || {}).rows || []).find((r) => String(r.task_id) === String(value));
			if (task) {
				row.task_name = task.task_name;
				row.uom = task.uom;
				row.total_qty = flt(task.contract_qty);
			}
		}
	}
	rp_set_state(frm, state);
	rp_schedule_compute(frm);
}

function rp_bind_resource_tabs(frm) {
	RP_TABS.forEach((cfg) => {
		const field = frm.get_field(cfg.field);
		if (!field || !field.$wrapper) return;
		field.$wrapper.off(".mpr");
		field.$wrapper.on("input.mpr", "input.mpr-input", function () { rp_on_input(frm, this); });
		field.$wrapper.on("change.mpr", "select.mpr-input", function () { rp_on_input(frm, this); });
		field.$wrapper.on("click.mpr", "button.mpr-action", function () {
			const action = this.getAttribute("data-action");
			const tab = this.getAttribute("data-tab");
			const row_index = this.getAttribute("data-row") === "" ? null : Number(this.getAttribute("data-row"));
			const state = rp_get_state(frm);
			if (action === "add-row") {
				state[tab].rows.push(rp_default_row(tab, frm));
				rp_set_state(frm, state);
				rp_compute_resource_plan(frm, { skip_seed: true });
			} else if (action === "remove-row" && row_index !== null) {
				state[tab].rows.splice(row_index, 1);
				rp_set_state(frm, state);
				rp_compute_resource_plan(frm, { skip_seed: true });
			} else if (action === "seed-tab") {
				rp_seed_resource_plan(frm, frm.__mp_distribution_data, { tab, silent: false });
			} else if (action === "recalc") {
				rp_compute_resource_plan(frm, { skip_seed: true });
			}
		});
	});
}
