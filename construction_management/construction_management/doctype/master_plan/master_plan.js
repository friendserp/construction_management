// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

const NS = "construction_management.construction_management.doctype.master_plan.master_plan";

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
	refresh(frm) {
		if (!frm.doc.project) {
			frm.dashboard.set_headline(
				__("Select a Project to load tasks and build the Ethiopian holiday calendar.")
			);
			render_working_days_html(frm, html_placeholder(__("Select a Project to build the calendar.")));
			render_matrix_html(frm, html_placeholder(__("Select a Project to build the distribution.")));
			return;
		}
		if (!frm.doc.start_date || !frm.doc.end_date) {
			frm.dashboard.set_headline(__("Set the project dates to build the holiday calendar."));
			render_working_days_html(frm, html_placeholder(__("Project dates are required.")));
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
			return;
		}
		// Restore the calendar + matrix preview from the saved data (HTML fields are not stored).
		recompute_working_days(frm, { silent: true });
		render_gantt_from_wbs(frm);
	},
});

frappe.ui.form.on("Holidayss", {
	day_type(frm) {
		schedule_recompute(frm);
	},
	from_date(frm, cdt, cdn) {
		set_row_total(frm, cdt, cdn);
		schedule_recompute(frm);
	},
	to_date(frm, cdt, cdn) {
		set_row_total(frm, cdt, cdn);
		schedule_recompute(frm);
	},
	holiday_name(frm) {
		schedule_recompute(frm);
	},
	holiday_add(frm) {
		schedule_recompute(frm);
	},
	holiday_remove(frm) {
		schedule_recompute(frm);
	},
});

frappe.ui.form.on("Activity Sequencing", {
	activity(frm) {
		schedule_recompute(frm);
	},
	predecessor_activity(frm) {
		schedule_recompute(frm);
	},
	relationship_type(frm) {
		schedule_recompute(frm);
	},
	lag_days(frm) {
		schedule_recompute(frm);
	},
	lead_days(frm) {
		schedule_recompute(frm);
	},
	activity_sequencing_remove(frm) {
		schedule_recompute(frm);
	},
});

frappe.ui.form.on("WBS", {
	duration(frm) {
		schedule_recompute(frm);
	},
});

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
				if (!t.name || seen.has(t.name)) return; // no duplicate task links
				seen.add(t.name);

				const row = frm.add_child("wbs");
				row.task_id = t.name;
				row.task_name = t.subject;
				row.uom = t.custom_unit;
				row.contract_qty = t.custom_contract_qty;
				row.task_unit_rate = t.custom_unit_rate;
				row.amount = t.custom_contract_amount;
				row.duration = flt(t.task_duration_in_days) || flt(t.duration);
				row.productivity = t.productivity;
				row.start_date = t.exp_start_date;
				row.finish_date = t.exp_end_date;
				row.executed_qty = t.custom_todate_exexuted_qty;
				row.remaining_qty = flt(t.custom_contract_qty) - flt(t.custom_todate_exexuted_qty);
			});
			frm.refresh_field("wbs");
			frm.dirty();

			frappe.show_alert({ message: __("{0} task(s) loaded", [seen.size]), indicator: "green" });
			build_monthly_distribution(frm, { silent: true });
			maybe_auto_schedule(frm);
		});
}

// The yearly view is a read-only roll-up of the very same monthly distribution,
// grouped by calendar year (Jan-Dec). It is rendered on demand from the computed
// data (nothing is stored), so it can never drift from the monthly plan.
function render_yearly_matrix(frm, data) {
	const field = frm.get_field("yearly_distribution_html");
	if (!field || !field.$wrapper) return;

	const cols = (data && data.columns) || [];
	const rows = (data && data.rows) || [];
	if (!cols.length || !rows.length) {
		field.$wrapper.html(
			html_placeholder(__("Nothing to distribute yet. Load tasks and build the distribution first."))
		);
		return;
	}

	const years = Array.from(new Set(cols.map((c) => String(c.key).slice(0, 4)))).sort();
	const year_wd = {};
	years.forEach((y) => (year_wd[y] = 0));
	cols.forEach((c) => (year_wd[String(c.key).slice(0, 4)] += flt(c.working_days)));

	const year_head = years
		.map((y) => `<th style="${DIST_TH}text-align:right">${frappe.utils.escape_html(y)}</th>`)
		.join("");
	const wd_cells = years
		.map((y) => `<td style="${DIST_WD}">${year_wd[y] || ""}</td>`)
		.join("");

	const col_total = {};
	years.forEach((y) => (col_total[y] = 0));

	const body = rows
		.map((r, i) => {
			const per_year = {};
			years.forEach((y) => (per_year[y] = { qty: 0, amount: 0 }));
			cols.forEach((c) => {
				const cell = r.cells && r.cells[c.key];
				if (!cell) return;
				const y = String(c.key).slice(0, 4);
				per_year[y].qty += flt(cell.qty);
				per_year[y].amount += flt(cell.amount);
			});
			const cells = years
				.map((y) => {
					const g = per_year[y];
					col_total[y] += g.qty;
					const pct = flt(r.contract_qty) ? (g.qty * 100) / flt(r.contract_qty) : 0;
					const title = `${y}: ${fmt_num(g.qty)} (${fmt_num(pct, 1)}%) \u00b7 ${fmt_num(g.amount)}`;
					return `<td title="${title}" style="${DIST_TD}text-align:right;${
						g.qty ? heat_style(pct) : ""
					}">${g.qty ? fmt_num(g.qty) : ""}</td>`;
				})
				.join("");
			return (
				`<tr>` +
				`<td style="${DIST_TD}color:#94a3b8">${frappe.utils.escape_html(
					r.series || r.task_id || String(i + 1)
				)}</td>` +
				`<td style="${DIST_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${frappe.utils.escape_html(
					r.task_name || r.task_id || ""
				)}">${frappe.utils.escape_html(r.task_name || r.task_id || "")}</td>` +
				`<td style="${DIST_TD}white-space:nowrap">${frappe.utils.escape_html(r.uom || "")}</td>` +
				`<td style="${DIST_TD}text-align:right;font-weight:600">${fmt_num(r.contract_qty)}</td>` +
				cells +
				`<td style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(
					r.distributed_qty
				)}</td>` +
				"</tr>"
			);
		})
		.join("");

	const foot = years
		.map((y) => `<td style="${DIST_TF}text-align:right">${col_total[y] ? fmt_num(col_total[y], 2) : ""}</td>`)
		.join("");
	const grand = rows.reduce((s, r) => s + flt(r.distributed_qty), 0);
	const wd_grand = years.reduce((s, y) => s + flt(year_wd[y]), 0);

	field.$wrapper.html(
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
			'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
			`<b>${__("Yearly Workload Distribution")}</b> &middot; ${rows.length} ${__(
				"items"
			)} &middot; ${years.length} ${__("year(s)")} &middot; ` +
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
			`<tr><td colspan="4" style="${DIST_WD_LBL}">${__(
				"Working days per year"
			)}</td>${wd_cells}<td style="${DIST_WD}font-weight:700">${wd_grand}</td></tr>` +
			body +
			"</tbody>" +
			`<tfoot><tr><td colspan="4" style="${DIST_TF}font-weight:600">${__(
				"Total"
			)}</td>${foot}<td style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(
				grand
			)}</td></tr></tfoot>` +
			"</table></div></div>"
	);
}

// ---------------------------------------------------------------------------
// Working days calendar (Ethiopian / standard ERPNext Holiday List)
// ---------------------------------------------------------------------------
function maybe_autobuild_calendar(frm, tries) {
	tries = tries == null ? 6 : tries;
	if (!frm.doc.project) return;
	if (frm.doc.start_date && frm.doc.end_date) {
		if (!frm.doc.holiday || !frm.doc.holiday.length) {
			build_working_calendar(frm, { silent: true });
		}
		return;
	}
	if (tries > 0) setTimeout(() => maybe_autobuild_calendar(frm, tries - 1), 400);
}

function build_working_calendar(frm, opts = {}) {
	if (!frm.doc.start_date || !frm.doc.end_date) {
		if (!opts.silent) {
			frappe.msgprint(__("Please set the Project Start Date and Project End Date first."));
		}
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

			if (data.country && !frm.doc.holiday_country) {
				frm.set_value("holiday_country", data.country);
			}
			if (data.weekly_off && data.weekly_off.indexOf(",") === -1 && !frm.doc.weekly_off) {
				frm.set_value("weekly_off", data.weekly_off);
			}

			frm.dirty();
			if (!opts.silent) {
				frappe.show_alert({
					message: __("{0} holiday row(s) between {1} and {2}", [
						(data.holidays || []).length,
						frm.doc.start_date,
						frm.doc.end_date,
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
			// On a plain form load we only refresh the preview, not the stored rows.
			if (opts.silent) {
				render_calendar_matrix(frm, data);
			} else {
				apply_working_days(frm, data);
			}
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
		for (let m = 1; m <= 12; m++) {
			child[String(m)] = row[String(m)] || 0;
		}
	});
	frm.refresh_field("no");
	render_calendar_matrix(frm, data);
	frm.dirty();
}

function render_working_days_html(frm, html) {
	const field = frm.get_field("working_days_html");
	if (field && field.$wrapper) {
		field.$wrapper.html(html || "");
	}
}

// ---------------------------------------------------------------------------
// Excel style working calendar matrix (top of the holiday table)
// ---------------------------------------------------------------------------
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
	const val = (v) =>
		flt(v) ? flt(v).toLocaleString("en-US", { maximumFractionDigits: 0 }) : "";

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

	const yearHead = yearGroups
		.map(
			(g) =>
				`<th colspan="${g.count}" style="${MPC_TH}text-align:center">${esc(String(g.year))}</th>`
		)
		.join("");
	const seasonHead = seasonGroups
		.map(
			(g) => `<th colspan="${g.count}" style="${MPC_TH}text-align:center">${esc(g.season || "")}</th>`
		)
		.join("");
	const monthHead = months
		.map((m) => `<th style="${MPC_TH}text-align:center;white-space:nowrap">${esc(m.label)}</th>`)
		.join("");

	const dataRow = (label, cellFn, total, opts = {}) => {
		const cells = months
			.map((m) => `<td style="${MPC_TD}text-align:right">${cellFn(m)}</td>`)
			.join("");
		return (
			`<tr><td style="${MPC_LABEL}">${esc(label)}</td>${cells}` +
			`<td style="${MPC_TOTAL}${opts.totalStyle || ""}">${total}</td></tr>`
		);
	};

	const rowsHtml =
		dataRow(
			__("Project Calendar"),
			(m) => `<span style="color:var(--text-muted,#8d99a6);white-space:nowrap">${esc(m.label)}</span>`,
			""
		) +
		dataRow(__("Calendar Days"), (m) => val(m.calendar_days), val(t.calendar_days)) +
		dataRow(__("Expected Rainy Days"), (m) => val(m.rainy_days), val(t.rainy_days)) +
		dataRow(__("Holidays"), (m) => val(m.holidays), val(t.holidays)) +
		dataRow(
			__("Holiday Leave Days"),
			(m) => val(m.holiday_leave_days),
			val(t.holiday_leave_days)
		) +
		dataRow(__("Sundays"), (m) => val(m.sundays), val(t.sundays)) +
		dataRow(
			__("Available (Working) Days"),
			(m) => `<b style="color:#0a7d33">${val(m.working_days)}</b>`,
			`<b style="color:#0a7d33">${val(t.working_days)}</b>`,
			{ totalStyle: "color:#0a7d33" }
		);

	field.$wrapper.html(
		`<div style="border:1px solid ${MPC_BORDER};border-radius:8px;overflow:hidden;margin:4px 0;` +
			`background:var(--fg-color,#fff)">` +
			`<div style="padding:8px 12px;background:${MPC_HEAD_BG};border-bottom:1px solid ${MPC_BORDER};` +
			`font-size:12px;color:var(--text-muted,#8d99a6)">` +
			`<b>${__("Working Calendar")}</b> &middot; ${esc(data.start_date || "")} &rarr; ${esc(
				data.end_date || ""
			)} &middot; ${__("Weekly Off")}: ${esc(data.weekly_off || "Sunday")}</div>` +
			`<div style="overflow:auto;max-height:70vh">` +
			`<table style="border-collapse:collapse;font-size:12px;width:100%">` +
			`<thead>` +
			`<tr><th style="${MPC_TH}"></th>${yearHead}` +
			`<th rowspan="2" style="${MPC_TH}text-align:right;vertical-align:middle">${__(
				"TOTAL"
			)}</th></tr>` +
			`<tr><th style="${MPC_TH}text-align:left">${__("Season")}</th>${seasonHead}</tr>` +
			`</thead>` +
			`<tbody>${rowsHtml}</tbody>` +
			`</table></div></div>`
	);
}

function render_matrix_html(frm, html) {
	const field = frm.get_field("monthly_distribution_html");
	if (field && field.$wrapper) {
		field.$wrapper.html(html || "");
	}
}

function html_placeholder(text) {
	return `<div style="border:1px dashed #cbd5e1;border-radius:10px;padding:12px 14px;color:#64748b;margin:4px 0">${frappe.utils.escape_html(
		text
	)}</div>`;
}

// ---------------------------------------------------------------------------
// Monthly / seasonal workload distribution (compact matrix)
// ---------------------------------------------------------------------------
function build_monthly_distribution(frm, opts = {}) {
	if (!frm.doc.start_date || !frm.doc.end_date) {
		if (!opts.silent) {
			frappe.msgprint(__("Please set the Project Start Date and Project End Date first."));
		}
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

	const tasks = frm.doc.wbs
		.filter((row) => row.task_id)
		.map((row) => ({
			task_id: row.task_id,
			task_name: row.task_name,
			series: row.series,
			uom: row.uom,
			contract_qty: row.contract_qty,
			task_unit_rate: row.task_unit_rate,
			start_date: row.start_date || frm.doc.start_date,
			finish_date: row.finish_date || frm.doc.end_date,
		}));

	const overrides = (frm.doc.distribution || [])
		.filter((d) => d.task_id && d.month && d.qty != null && d.qty !== "")
		.map((d) => ({
			task_id: d.task_id,
			month: d.month,
			qty: d.qty,
		}));

	frappe.call({
		method: `${NS}.get_monthly_distribution`,
		args: {
			holiday_list: frm.doc.holiday_list,
			country: frm.doc.holiday_country || "ET",
			holidays: holidays,
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			tasks: tasks,
			overrides: overrides,
			season_length_months: frm.doc.season_length_months || 4,
			weekly_off: frm.doc.weekly_off,
		},
		freeze: !opts.silent,
		freeze_message: __("Distributing workload across months..."),
		callback(r) {
			const data = r.message || {};
			render_monthly_matrix(frm, data);
			render_yearly_matrix(frm, data);
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

	if (!cols.length || !rows.length) {
		render_matrix_html(
			frm,
			html_placeholder(__("Nothing to distribute yet. Load tasks and build the calendar first."))
		);
		return;
	}

	// Season header spans (consecutive months of the same season).
	const groups = [];
	cols.forEach((c) => {
		const last = groups[groups.length - 1];
		if (last && last.season === c.season) last.count++;
		else groups.push({ season: c.season, count: 1 });
	});
	const season_cells = groups
		.map(
			(g) =>
				`<th colspan="${g.count}" style="${DIST_TH}text-align:center">${frappe.utils.escape_html(
					g.season || ""
				)}</th>`
		)
		.join("");
	const number_cells = cols
		.map((c) => `<th style="${DIST_TH}color:#64748b;font-weight:500">${c.month_index}</th>`)
		.join("");
	const month_cells = cols
		.map((c) => `<th style="${DIST_TH}white-space:nowrap">${frappe.utils.escape_html(c.label)}</th>`)
		.join("");

	const wd_total = cols.reduce((s, c) => s + flt(c.working_days), 0);
	const wd_cells = cols
		.map((c) => `<td style="${DIST_WD}">${c.working_days == null ? "" : c.working_days}</td>`)
		.join("");

	const body = rows
		.map((r, i) => {
			const task_id = String(r.task_id == null ? "" : r.task_id);
			const cells = cols
				.map((c) => {
					const cell = r.cells[c.key];
					const qty = cell ? flt(cell.qty) : 0;
					const manual = !!(cell && cell.manual);
					const pct = cell ? cell.percent : 0;
					const title = `${frappe.utils.escape_html(c.label)}: ${fmt_num(
						qty
					)} (${fmt_num(pct, 1)}%)${manual ? " \u2022 " + __("manual") : ""}`;
					return (
						`<td title="${title}" style="${DIST_TD}padding:2px;text-align:right;${heat_style(
							pct
						)}">` +
						`<input type="number" step="any" min="0" class="mpdm-cell"\
 data-task="${frappe.utils.escape_html(task_id)}" data-month="${frappe.utils.escape_html(
							c.key
						)}" value="${qty ? qty : ""}" ` +
						`style="${MPDM_INPUT}${manual ? MPDM_INPUT_MANUAL : ""}"></td>`
					);
				})
				.join("");
			return (
				`<tr class="mpdm-item" data-task="${frappe.utils.escape_html(
					task_id
				)}" data-qty="${flt(r.contract_qty)}">` +
				`<td style="${DIST_TD}color:#94a3b8">${frappe.utils.escape_html(
					r.series || r.task_id || String(i + 1)
				)}</td>` +
				`<td style="${DIST_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${frappe.utils.escape_html(
					r.task_name || r.task_id || ""
				)}">${frappe.utils.escape_html(r.task_name || r.task_id || "")}</td>` +
				`<td style="${DIST_TD}white-space:nowrap">${frappe.utils.escape_html(r.uom || "")}</td>` +
				`<td style="${DIST_TD}text-align:right;font-weight:600">${fmt_num(
					r.contract_qty
				)}</td>` +
				cells +
				`<td class="mpdm-rowtotal" style="${DIST_TF}text-align:right;font-weight:600">${fmt_num(
					r.distributed_qty
				)}</td>` +
				"</tr>"
			);
		})
		.join("");

	const col_total = {};
	cols.forEach((c) => (col_total[c.key] = 0));
	rows.forEach((r) => {
		cols.forEach((c) => {
			const cell = r.cells[c.key];
			if (cell) col_total[c.key] += flt(cell.qty);
		});
	});
	const grand_total = rows.reduce((s, r) => s + flt(r.distributed_qty), 0);

	const foot_cells = cols
		.map(
			(c) =>
				`<td class="mpdm-foot" data-month="${frappe.utils.escape_html(
					c.key
				)}" style="${DIST_TF}text-align:right">${
					col_total[c.key] ? fmt_num(col_total[c.key], 2) : ""
				}</td>`
		)
		.join("");

	field.$wrapper.html(
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
			'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
			`<b>${__("Workload Distribution")}</b> &middot; ${rows.length} ${__(
				"items"
			)} &middot; ${cols.length} ${__("months")} &middot; ` +
			`<span style="color:#92400e">${__(
				"edit any month cell to override; highlighted cells are manual"
			)}</span></div>` +
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
			`<tr><td colspan="4" style="${DIST_WD_LBL}">${__(
				"Available working days of months"
			)}</td>${wd_cells}<td style="${DIST_WD}font-weight:700">${wd_total}</td></tr>` +
			body +
			"</tbody>" +
			`<tfoot><tr><td colspan="4" style="${DIST_TF}font-weight:600">${__(
				"Total"
			)}</td>${foot_cells}<td class="mpdm-grand" style="${DIST_TF}text-align:right;font-weight:700">${fmt_num(
				grand_total
			)}</td></tr></tfoot>` +
			"</table></div></div>"
	);

	bind_distribution_cells(frm);
}

function bind_distribution_cells(frm) {
	const field = frm.get_field("monthly_distribution_html");
	if (!field || !field.$wrapper) return;
	// `input` fires while typing so a keyboard save (Ctrl+S) can never miss an edit.
	field.$wrapper.off("input.mpdm").on("input.mpdm", "input.mpdm-cell", function () {
		on_distribution_cell_edit(frm, this);
	});
}

function on_distribution_cell_edit(frm, input) {
	const $in = $(input);
	const task_id = String($in.attr("data-task") || "");
	const month = String($in.attr("data-month") || "");
	const raw = $in.val();
	set_distribution_override(frm, task_id, month, raw);
	const has_val = raw !== "" && raw != null && !isNaN(flt(raw));
	$in.attr("style", MPDM_INPUT + (has_val ? MPDM_INPUT_MANUAL : ""));
	refresh_row_total($in.closest("tr"));
	refresh_distribution_footer(frm);
}

function set_distribution_override(frm, task_id, month, raw) {
	frm.doc.distribution = frm.doc.distribution || [];
	const list = frm.doc.distribution;
	// Drop blank rows left over from older builds so they never pollute the save.
	for (let i = list.length - 1; i >= 0; i--) {
		if (!list[i].task_id || !list[i].month) list.splice(i, 1);
	}
	const row = list.find(
		(d) => String(d.task_id) === task_id && String(d.month) === month
	);
	const has_val = raw !== "" && raw != null && !isNaN(flt(raw));
	if (!has_val) {
		if (row) {
			list.splice(list.indexOf(row), 1);
			frm.dirty();
		}
		return;
	}
	const target =
		row || frappe.model.add_child(frm.doc, "Master Plan Distribution", "distribution");
	target.task_id = task_id;
	target.month = month;
	target.qty = flt(raw);
	frm.dirty();
}

function refresh_row_total($row) {
	let sum = 0;
	$row.find("input.mpdm-cell").each(function () {
		sum += flt($(this).val());
	});
	const target = flt($row.attr("data-qty"));
	const $cell = $row.find(".mpdm-rowtotal");
	$cell.text(fmt_num(sum, 2) || "0");
	const diff = Math.round((sum - target) * 100) / 100;
	if (Math.abs(diff) > 0.0001) {
		$cell.attr("title", __("Differs from Project Qty by {0}", [diff]));
		$cell.css("color", "#b91c1c");
	} else {
		$cell.removeAttr("title");
		$cell.css("color", "");
	}
}

function refresh_distribution_footer(frm) {
	const field = frm.get_field("monthly_distribution_html");
	if (!field || !field.$wrapper) return;
	const totals = {};
	let grand = 0;
	field.$wrapper.find("tr.mpdm-item").each(function () {
		$(this)
			.find("input.mpdm-cell")
			.each(function () {
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
// Activity sequencing, CPM schedule, Gantt chart and resource loading
// ---------------------------------------------------------------------------
function maybe_auto_schedule(frm) {
	if (!frm.doc.project || !frm.doc.start_date || !frm.doc.end_date) return;
	if (!frm.doc.wbs || !frm.doc.wbs.length) return;
	run_schedule_engine(frm, { silent: true });
}

// When the user has not defined relationships yet, chain the tasks in WBS order
// (Finish to Start) so a real start/finish window can be computed for each.
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
		if (!opts.silent) {
			frappe.msgprint(__("Please set the Project Start Date and Project End Date first."));
		}
		return;
	}
	ensure_sequencing(frm);

	const tasks = (frm.doc.wbs || [])
		.filter((r) => r.task_id)
		.map((r) => ({
			task_id: r.task_id,
			task_name: r.task_name,
			duration: flt(r.duration),
		}));
	const sequencing = (frm.doc.activity_sequencing || []).map((r) => ({
		activity: r.activity,
		predecessor_activity: r.predecessor_activity,
		relationship_type: r.relationship_type,
		lag_days: r.lag_days,
		lead_days: r.lead_days,
	}));
	const holidays = (frm.doc.holiday || []).map((h) => ({
		day_type: h.day_type || "Holiday",
		from_date: h.from_date,
		to_date: h.to_date || h.from_date,
	}));

	frappe.call({
		method: `${NS}.compute_schedule`,
		args: {
			project: frm.doc.project,
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			holidays: holidays,
			tasks: tasks,
			sequencing: sequencing,
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
					message: __("Project duration: {0} working day(s)", [
						data.critical_path_duration_in_day,
					]),
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

	build_monthly_distribution(frm, { silent: true });
}

// ---------------------------------------------------------------------------
// Gantt chart (self-contained HTML/CSS, no external library)
// ---------------------------------------------------------------------------
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

	let min = null;
	let max = null;
	rows.forEach((r) => {
		const s = toDate(r.start_date);
		const e = toDate(r.finish_date);
		if (!min || s < min) min = s;
		if (!max || e > max) max = e;
	});
	const total = Math.max(1, days(min, max) + 1);
	const off = (d) => days(min, d) / total;

	// Month axis.
	const months = [];
	let cur = new Date(min.getFullYear(), min.getMonth(), 1);
	while (cur <= max) {
		const mStart = cur < min ? min : cur;
		const monthEnd = new Date(cur.getFullYear(), cur.getMonth() + 1, 0);
		const mEnd = monthEnd > max ? max : monthEnd;
		months.push({
			label: new Date(cur.getFullYear(), cur.getMonth(), 1).toLocaleString("en-US", {
				month: "short",
				year: "2-digit",
			}),
			left: off(mStart),
			width: (days(mStart, mEnd) + 1) / total,
		});
		cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
	}
	const monthHead = months
		.map(
			(m) =>
				`<div style="position:absolute;left:${(m.left * 100).toFixed(4)}%;` +
				`width:${(m.width * 100).toFixed(4)}%;border-left:1px solid #e2e8f0;box-sizing:border-box;` +
				`padding:2px 4px;font-size:10px;color:#64748b;white-space:nowrap;overflow:hidden">${esc(
					m.label
				)}</div>`
		)
		.join("");

	const body = rows
		.map((r) => {
			const left = off(r.start_date) * 100;
			const width = ((days(r.start_date, r.finish_date) + 1) / total) * 100;
			const color = r.is_critical ? "#dc2626" : "#2563eb";
			const label = `${r.task_name || r.task_id} (${r.start_date} → ${r.finish_date})`;
			return (
				`<tr><td style="padding:2px 6px;border:1px solid #eef2f7;font-size:11px;max-width:280px;` +
				`white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(label)}">${esc(
					r.task_name || r.task_id
				)}</td>` +
				`<td style="padding:0;border:1px solid #eef2f7;position:relative;height:22px">` +
				`<div title="${esc(label)}" style="position:absolute;top:3px;height:16px;left:${left.toFixed(
					4
				)}%;width:${width.toFixed(4)}%;background:${color};border-radius:3px"></div>` +
				`</td></tr>`
			);
		})
		.join("");

	field.$wrapper.html(
		`<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">` +
			`<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">` +
			`<b>${__("Gantt Chart")}</b> &middot; <span style="color:#dc2626">\u25a0</span> ${__(
				"Critical"
			)} &middot; <span style="color:#2563eb">\u25a0</span> ${__("Non-critical")}</div>` +
			`<div style="overflow:auto;max-height:70vh">` +
			`<table style="border-collapse:collapse;font-size:11px;width:100%">` +
			`<thead><tr><th style="padding:5px 8px;border:1px solid #e2e8f0;background:#f1f5f9;` +
			`text-align:left;width:280px">${__("Activity")}</th>` +
			`<th style="padding:0;border:1px solid #e2e8f0;background:#f1f5f9;position:relative;height:22px">${monthHead}</th>` +
			`</tr></thead><tbody>${body}</tbody></table></div></div>`
	);
}

// Re-draw the chart from the saved WBS rows on a plain form load.
function render_gantt_from_wbs(frm) {
	if (!frm.doc.wbs || !frm.doc.wbs.length) return;
	const rows = frm.doc.wbs
		.filter((r) => r.task_id && r.start_date && r.finish_date)
		.map((r) => ({
			task_id: r.task_id,
			task_name: r.task_name,
			start_date: r.start_date,
			finish_date: r.finish_date,
			is_critical: flt(r.total_float) <= 0,
		}));
	if (rows.length) render_gantt(frm, rows);
}

// ---------------------------------------------------------------------------
// Resource loading - explode each task's Cost Break Down into the schedule
// ---------------------------------------------------------------------------
function load_task_resources(frm, opts = {}) {
	if (!frm.doc.wbs || !frm.doc.wbs.length) {
		if (!opts.silent) frappe.msgprint(__("Load the project tasks first."));
		return;
	}
	const tasks = frm.doc.wbs
		.filter((r) => r.task_id)
		.map((r) => ({
			task_id: r.task_id,
			task_name: r.task_name,
			start_date: r.start_date,
			finish_date: r.finish_date,
		}));

	frappe.call({
		method: `${NS}.get_task_resources`,
		args: { project: frm.doc.project, tasks: tasks },
		freeze: !opts.silent,
		freeze_message: __("Loading task resources from the Cost Break Downs..."),
		callback(r) {
			const d = r.message || {};
			fill_child_table(frm, "task_machinery_list", d.machinery || []);
			fill_child_table(frm, "task_manpower_list", d.manpower || []);
			fill_child_table(frm, "task_material_list", d.material || []);
			frm.dirty();
			if (!opts.silent) {
				frappe.show_alert({
					message: __("{0} machinery, {1} manpower and {2} material row(s) loaded.", [
						(d.machinery || []).length,
						(d.manpower || []).length,
						(d.material || []).length,
					]),
					indicator: "green",
				});
			}
		},
	});
}

function fill_child_table(frm, table, rows) {
	frm.clear_table(table);
	rows.forEach((r) => {
		const c = frm.add_child(table);
		Object.keys(r).forEach((k) => {
			c[k] = r[k];
		});
	});
	frm.refresh_field(table);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const TH =
	"padding:5px 8px;border:1px solid #e2e8f0;background:#f1f5f9;position:sticky;top:0;z-index:1;font-weight:600;";
const TD = "padding:4px 8px;border:1px solid #eef2f7;";
const TF = "padding:5px 8px;border:1px solid #e2e8f0;background:#f8fafc;";

// Workload distribution matrix (season grouped, month index + label header).
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

// Working calendar matrix - uses Frappe's own theme variables so it matches the desk UI.
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

