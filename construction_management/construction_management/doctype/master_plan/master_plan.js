// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

const NS = "construction_management.construction_management.doctype.master_plan.master_plan";

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
	get_task_resources(frm) {
		load_task_resources(frm);
	},
	season_length_months(frm) {
		if (frm.doc.start_date && frm.doc.end_date) schedule_recompute(frm);
	},
	validate(frm) {
		validate_distribution_totals(frm, { throw: true });
	},
	refresh(frm) {
		if (!frm.doc.project) {
			frm.dashboard.set_headline(
				__("Select a Project to load tasks and build the Ethiopian holiday calendar.")
			);
			render_working_days_html(frm, html_placeholder(__("Select a Project to build the calendar.")));
			render_matrix_html(frm, html_placeholder(__("Select a Project to build the distribution.")));
			render_cost_matrix(frm, {});
			clear_resource_tables(frm);
			return;
		}
		if (!frm.doc.start_date || !frm.doc.end_date) {
			frm.dashboard.set_headline(__("Set the project dates to build the holiday calendar."));
			render_working_days_html(frm, html_placeholder(__("Project dates are required.")));
			render_cost_matrix(frm, {});
			clear_resource_tables(frm);
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
			clear_resource_tables(frm);
			return;
		}
		recompute_working_days(frm, { silent: true });
		render_gantt_from_wbs(frm);

		// If the resources child tables are empty but WBS exists, auto-load from CBD.
		const has_resources =
			(frm.doc.project_machinery_list || []).length ||
			(frm.doc.project_manpower_list || []).length ||
			(frm.doc.project_material_list || []).length;
		if (!has_resources && frm.doc.wbs && frm.doc.wbs.length) {
			load_task_resources(frm, { silent: true });
		}
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
			frappe.show_alert({ message: __("{0} task(s) loaded", [seen.size]), indicator: "green" });
			load_task_resources(frm, { silent: true });
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

	// Resources go along for the ride - one server call returns all 6 tables
	const machinery = (frm.doc.project_machinery_list || []).map((r) => ({
		task_id: r.task_id, type: r.type, qty: r.qty, uf: r.uf,
		task_duration_in_hour: r.task_duration_in_hour,
		total_hourly_cost: r.total_hourly_cost, total_cost: r.total_cost,
	}));
	const manpower = (frm.doc.project_manpower_list || []).map((r) => ({
		task_id: r.task_id, job_title: r.job_title, qty: r.qty, uf: r.uf,
		task_duration_in_hour: r.task_duration_in_hour,
		total_hourly_cost: r.total_hourly_cost, total_cost: r.total_cost,
	}));
	const material = (frm.doc.project_material_list || []).map((r) => ({
		task_id: r.task_id, item1: r.item1, uom: r.uom, qty: r.qty,
		unit_price: r.unit_price, total_cost: r.total_cost,
	}));

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
				machinery: (data.machinery || []).length,
				manpower: (data.manpower || []).length,
				material: (data.material || []).length,
			});
			render_monthly_matrix(frm, data);
			render_cost_matrix(frm, data);
			render_yearly_matrix(frm, data);
			render_resource_tables(frm, data);
			if (!opts.silent) {
				frappe.show_alert({
					message: __("{0} task(s) over {1} month(s) · {2} machinery · {3} manpower · {4} material", [
						(data.rows || []).length,
						(data.columns || []).length,
						(data.machinery || []).length,
						(data.manpower || []).length,
						(data.material || []).length,
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
		return `<tr class="mpdm-item" data-task="${frappe.utils.escape_html(task_id)}" data-qty="${flt(r.contract_qty)}">` +
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
	const target = flt($row.attr("data-qty"));
	const $cell = $row.find(".mpdm-rowtotal");
	$cell.text(fmt_num(sum, 2));
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
// Resource loading (CBD → child tables)
// ---------------------------------------------------------------------------
function load_task_resources(frm, opts = {}) {
	if (!frm.doc.wbs || !frm.doc.wbs.length) {
		clear_resource_tables(frm);
		if (!opts.silent) frappe.msgprint(__("Load the project tasks first."));
		return;
	}
	const tasks = frm.doc.wbs.filter((r) => r.task_id).map((r) => ({
		task_id: r.task_id, task_name: r.task_name,
		start_date: r.start_date, finish_date: r.finish_date,
	}));

	frappe.call({
		method: `${NS}.get_task_resources`,
		args: { project: frm.doc.project, tasks },
		freeze: !opts.silent,
		freeze_message: __("Loading task resources from the Cost Break Downs..."),
		callback(r) {
			const d = (r && r.message) || {};
			const m = d.machinery || [];
			const p = d.manpower || [];
			const mat = d.material || [];

			if (!m.length && !p.length && !mat.length) {
				clear_resource_tables(frm);
				if (!opts.silent) {
					frappe.msgprint({
						title: __("No Resource Data"),
						indicator: "orange",
						message: __("The tasks in this project have no Cost Break Down entries. Add a Cost Break Down to each Task master and try again."),
					});
				}
				return;
			}
			fill_child_table(frm, "project_machinery_list", m);
			fill_child_table(frm, "project_manpower_list", p);
			fill_child_table(frm, "project_material_list", mat);
			frm.dirty();
			// Rebuild distribution + resource tables (one server call)
			build_monthly_distribution(frm, { silent: true });
			if (!opts.silent) {
				frappe.show_alert({
					message: __("{0} machinery, {1} manpower and {2} material row(s) loaded.", [m.length, p.length, mat.length]),
					indicator: "green",
				});
			}
		},
		error(r) {
			clear_resource_tables(frm);
			console.error("Master Plan: get_task_resources failed", r);
			if (!opts.silent) {
				frappe.msgprint({
					title: __("Could Not Load Resources"),
					indicator: "red",
					message: __("The server did not return resource data. Open the browser console and the Frappe Error Log for details."),
				});
			}
		},
	});
}

function fill_child_table(frm, table, rows) {
	frm.clear_table(table);
	rows.forEach((r) => {
		const c = frm.add_child(table);
		Object.keys(r).forEach((k) => { c[k] = r[k]; });
	});
	frm.refresh_field(table);
}

// ---------------------------------------------------------------------------
// Resource distribution tables (season grouped, mirrors the workload matrix)
// ---------------------------------------------------------------------------
const RESOURCE_TABLES = [
	{
		kind: "machinery",
		key: "machinery",
		fields: ["machinery_distribution", "machinery_distirbution"],
		title: __("Machinery Distribution by Season"),
		metric_label: __("No"),
	},
	{
		kind: "manpower",
		key: "manpower",
		fields: ["manpower_distribution", "manpower_distirbution"],
		title: __("Manpower Distribution by Season"),
		metric_label: __("Hours"),
	},
	{
		kind: "material",
		key: "material",
		fields: ["material_distribution", "material_distirbution"],
		title: __("Material Distribution by Season"),
		metric_label: __("Qty"),
	},
];

function resolve_field(frm, names) {
	for (const n of names) if (frm.get_field(n)) return n;
	return null;
}

function render_resource_tables(frm, data) {
	mp_log("render_resource_tables data", {
		columns: (data.columns || []).length,
		machinery: (data.machinery || []).length,
		manpower: (data.manpower || []).length,
		material: (data.material || []).length,
	});
	RESOURCE_TABLES.forEach((cfg) => {
		const fname = resolve_field(frm, cfg.fields);
		if (!fname) {
			mp_log(`render_resource_tables missing field for ${cfg.kind}`, cfg.fields);
			return;
		}
		render_resource_table(frm, fname, cfg, data[cfg.key] || [], data.columns || []);
	});
}

function clear_resource_tables(frm) {
	RESOURCE_TABLES.forEach((cfg) => {
		const fname = resolve_field(frm, cfg.fields);
		if (fname) render_resource_table(frm, fname, cfg, [], []);
	});
}

function render_resource_table(frm, field_name, cfg, rows, columns) {
	const field = frm.get_field(field_name);
	if (!field || !field.$wrapper) return;

	mp_log(`render_resource_table ${cfg.kind}`, {
		field: field_name,
		rows: (rows || []).length,
		columns: (columns || []).length,
		row_summary: (rows || []).map((r) => ({
			name: r.name,
			unit: r.unit,
			total_metric: r.total_metric,
			total_cost: r.total_cost,
		})),
	});
	if (!rows || !rows.length || !columns || !columns.length) {
		field.$wrapper.html(html_placeholder(
			__("No resources found. Add a Cost Break Down to each Task master, then reopen the form (or click '{0}').",
				[__("Get Task Resources")])
		));
		return;
	}

	const esc = frappe.utils.escape_html;
	const metric_key = cfg.kind === "manpower" ? "hours" : "qty";
	const metric_label = cfg.metric_label;

	// Same season grouping as the workload matrix
	const groups = [];
	columns.forEach((c) => {
		const last = groups[groups.length - 1];
		if (last && last.season === c.season) last.count++;
		else groups.push({ season: c.season, count: 1 });
	});
	const season_cells = groups.map((g) =>
		`<th colspan="${g.count}" style="${DIST_TH}text-align:center">${esc(g.season || "")}</th>`
	).join("");
	const number_cells = columns.map((c) =>
		`<th style="${DIST_TH}color:#64748b;font-weight:500">${c.month_index}</th>`
	).join("");
	const month_cells = columns.map((c) =>
		`<th style="${DIST_TH}white-space:nowrap">${esc(c.label)}</th>`
	).join("");

	const col_totals = {};
	columns.forEach((c) => (col_totals[c.key] = { metric: 0, cost: 0 }));

	const body = rows.map((r) => {
		const cells = columns.map((c) => {
			const cell = (r.cells && r.cells[c.key]) || { qty: 0, hours: 0, cost: 0 };
			const metric = flt(cell[metric_key]);
			const cost = flt(cell.cost);
			col_totals[c.key].metric += metric;
			col_totals[c.key].cost += cost;
			const title = `${esc(c.label)}: ${fmt_num(metric)} ${metric_label} · ${fmt_num(cost)}`;
			return `<td title="${title}" style="${DIST_TD}text-align:right;padding:2px 4px">` +
				`<div style="font-weight:600;color:#0f172a">${metric ? fmt_num(metric) : ""}</div>` +
				`<div style="font-size:10px;color:#64748b">${cost ? fmt_num(cost) : ""}</div></td>`;
		}).join("");

		return `<tr>` +
			`<td style="${DIST_TD}max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(r.name || "")}">${esc(r.name || "")}</td>` +
			`<td style="${DIST_TD}white-space:nowrap">${esc(r.unit || "")}</td>` +
			`<td style="${DIST_TD}text-align:right;font-weight:600">${fmt_num(r.total_metric)}</td>` +
			cells +
			`<td style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(r.total_metric)}</td>` +
			`<td style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(r.total_cost)}</td>` +
			`</tr>`;
	}).join("");

	const foot_cells = columns.map((c) => {
		const t = col_totals[c.key];
		return `<td style="${DIST_TF}text-align:right;padding:2px 4px">` +
			`<div style="font-weight:600;color:#0f172a">${t.metric ? fmt_num(t.metric) : ""}</div>` +
			`<div style="font-size:10px;color:#64748b">${t.cost ? fmt_num(t.cost) : ""}</div></td>`;
	}).join("");

	const grand_metric = rows.reduce((s, r) => s + flt(r.total_metric), 0);
	const grand_cost = rows.reduce((s, r) => s + flt(r.total_cost), 0);

	field.$wrapper.html(
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
		'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
		`<b>${cfg.title}</b> · ${rows.length} ${__("items")} · ${columns.length} ${__("months")} · ` +
		`<span style="color:#64748b">${__("derived from the workload distribution")}</span></div>` +
		'<div style="overflow:auto;max-height:75vh">' +
		'<table style="border-collapse:collapse;font-size:12px;width:100%">' +
		"<thead>" +
		`<tr><th rowspan="3" style="${DIST_TH}text-align:left">${__("Resource")}</th>` +
		`<th rowspan="3" style="${DIST_TH}">${__("Unit")}</th>` +
		`<th rowspan="3" style="${DIST_TH}text-align:right">${__("Project")} ${metric_label}</th>` +
		season_cells +
		`<th rowspan="3" style="${DIST_TH}text-align:right">${__("TOTAL")} ${metric_label}</th>` +
		`<th rowspan="3" style="${DIST_TH}text-align:right">${__("TOTAL")} ${__("Cost")}</th></tr>` +
		`<tr>${number_cells}</tr>` +
		`<tr>${month_cells}</tr>` +
		"</thead>" +
		`<tbody>${body}</tbody>` +
		`<tfoot><tr><td colspan="3" style="${DIST_TF}font-weight:600">${__("Total")}</td>${foot_cells}` +
		`<td style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(grand_metric)}</td>` +
		`<td style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(grand_cost)}</td>` +
		`</tr></tfoot>` +
		"</table></div></div>"
	);
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
