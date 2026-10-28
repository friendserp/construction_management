// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

const NS =
	"construction_management.construction_management.doctype.operational_plan.operational_plan";
const MASTER_NS =
	"construction_management.construction_management.doctype.master_plan.master_plan";

// Month number -> column field prefix on the workload / cashflow tables.
const OP_MONTHS = {
	1: "jan",
	2: "feb",
	3: "mar",
	4: "apr",
	5: "may",
	6: "jun",
	7: "jul",
	8: "aug",
	9: "sep",
	10: "oct",
	11: "nov",
	12: "dec",
};
const OP_MONTH_LABELS = [
	"Jan",
	"Feb",
	"Mar",
	"Apr",
	"May",
	"Jun",
	"Jul",
	"Aug",
	"Sep",
	"Oct",
	"Nov",
	"Dec",
];

const OP_TH =
	"padding:6px 8px;border:1px solid #e2e8f0;background:#f1f5f9;font-weight:600;text-align:center;position:sticky;top:0;z-index:2";
const OP_TD = "padding:4px 6px;border:1px solid #eef2f7;white-space:nowrap;";
const OP_TF = "padding:5px 6px;border:1px solid #e2e8f0;background:#f8fafc;font-weight:600;";

// Same style tokens the Master Plan uses for its working calendar matrix.
const MPC_BORDER = "var(--border-color,#d1d8dd)";
const MPC_HEAD_BG = "var(--subtle-fg,#f4f5f6)";
const MPC_TH = `padding:6px 8px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);`;
const MPC_LABEL = `padding:6px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);white-space:nowrap;text-align:left;`;
const MPC_TD = `padding:5px 8px;border:1px solid ${MPC_BORDER};color:var(--text-color,#1f272e);`;
const MPC_TOTAL = `padding:5px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:700;text-align:right;`;

frappe.ui.form.on("Operational Plan", {
	master_plan_name(frm) {
		prefill_from_master(frm);
	},
	year(frm) {
		apply_year_dates(frm, true);
	},
	refresh(frm) {
		load_master_years(frm).then(() => {
			if (!frm.doc.master_plan_name) {
				frm.dashboard.set_headline(
					__("Select a Master Plan, choose a Year, then the plan loads automatically.")
				);
				render_op_calendar_html(frm, op_placeholder(__("Select a Master Plan first.")));
				render_op_distribution_html(frm, op_placeholder(__("Select a Master Plan first.")));
				return;
			}
			if (!frm.doc.start_date || !frm.doc.end_date) {
				frm.dashboard.set_headline(__("Choose a Year to fill the Start / End dates."));
				render_op_calendar_html(frm, op_placeholder(__("Choose a Year.")));
				render_op_distribution_html(frm, op_placeholder(__("Choose a Year.")));
				return;
			}
			frm.dashboard.set_headline(
				__("Master Plan: {0} · {1} → {2}", [
					frm.doc.master_plan_name,
					frm.doc.start_date,
					frm.doc.end_date,
				])
			);
			// HTML fields are not persisted: restore the previews from the saved data.
			render_op_distribution_html_from_doc(frm);
			restore_op_calendar_html(frm);
			render_op_gantt(frm);
		});
	},
	get_calender(frm) {
		load_operational_calendar(frm);
	},
	get_task_monthly_distribution(frm) {
		load_operational_plan(frm);
	},
	get_critical_path(frm) {
		load_operational_schedule(frm);
	},
	get_resources(frm) {
		frappe.msgprint(__("Resource scheduling is not wired yet."));
	},
});

function prefill_from_master(frm) {
	if (!frm.doc.master_plan_name) return;
	frappe.db.get_doc("Master Plan", frm.doc.master_plan_name).then((doc) => {
		const updates = {};
		if (doc.project) updates.project = doc.project;
		if (doc.consultant) updates.consultant = doc.consultant;
		if (doc.client) updates.client = doc.client;
		if (Object.keys(updates).length) frm.set_value(updates);

		// Populate the Year dropdown with the years the Master Plan covers,
		// then pick the current (or first) year and load the plan.
		load_master_years(frm, doc).then((years) => {
			if (!years.length) return;
			const now = String(new Date().getFullYear());
			const pick = years.find((y) => y.value === now) || years[0];
			// set_value triggers the year(frm) handler -> fills dates + loads the plan.
			const unchanged = String(frm.doc.year || "") === pick.value;
			frm.set_value("year", pick.value);
			if (unchanged) apply_year_dates(frm, true);
		});
	});
}

// Compute the calendar years the Master Plan spans, each clipped to the plan window.
function master_plan_years(doc) {
	const out = [];
	if (!doc || !doc.start_date || !doc.end_date) return out;
	const s = frappe.datetime.str_to_obj(doc.start_date);
	const e = frappe.datetime.str_to_obj(doc.end_date);
	for (let y = s.getFullYear(); y <= e.getFullYear(); y++) {
		const from = frappe.datetime.obj_to_str(new Date(y, 0, 1)).slice(0, 10);
		const to = frappe.datetime.obj_to_str(new Date(y, 11, 31)).slice(0, 10);
		out.push({
			value: String(y),
			start_date: from < doc.start_date ? doc.start_date : from,
			end_date: to > doc.end_date ? doc.end_date : to,
		});
	}
	return out;
}

function load_master_years(frm, doc) {
	if (!frm.doc.master_plan_name) {
		frm.set_df_property("year", "options", "");
		frm.__mp_years = [];
		return Promise.resolve([]);
	}
	const p = doc ? Promise.resolve(doc) : frappe.db.get_doc("Master Plan", frm.doc.master_plan_name);
	return p.then((master) => {
		const years = master_plan_years(master);
		frm.__mp_years = years;
		frm.set_df_property("year", "options", years.map((y) => y.value).join("\n"));
		frm.refresh_field("year");
		return years;
	});
}

// Set Start / End from the selected Year, clipped to the Master Plan window.
function apply_year_dates(frm, auto_load) {
	if (!frm.doc.year) return;
	const years = frm.__mp_years || [];
	const y = years.find((x) => x.value === String(frm.doc.year));
	if (!y) return;
	if (frm.doc.start_date !== y.start_date) frm.set_value("start_date", y.start_date);
	if (frm.doc.end_date !== y.end_date) frm.set_value("end_date", y.end_date);
	if (auto_load) load_operational_plan(frm);
}

function fetch_operational_plan(frm) {
	if (!frm.doc.master_plan_name) {
		frappe.msgprint(__("Please select a Master Plan first."));
		return Promise.resolve(null);
	}
	if (!frm.doc.start_date || !frm.doc.end_date) {
		frappe.msgprint(__("Please set the Start Date and End Date."));
		return Promise.resolve(null);
	}
	return frappe
		.call({
			method: `${NS}.get_operational_plan_data`,
			args: {
				master_plan: frm.doc.master_plan_name,
				start_date: frm.doc.start_date,
				end_date: frm.doc.end_date,
			},
			freeze: true,
			freeze_message: __("Building operational plan from the Master Plan..."),
		})
		.then((r) => r.message || null);
}

function load_operational_calendar(frm) {
	fetch_operational_plan(frm).then((data) => {
		if (!data) return;
		apply_operational_calendar(frm, data.calendar);
		render_op_calendar_matrix(frm, data.calendar);
		frm.dirty();
		frappe.show_alert({
			message: __("Working days loaded: {0}", [
				flt((data.calendar && data.calendar.total_working_days) || 0),
			]),
			indicator: "green",
		});
	});
}

function load_operational_plan(frm) {
	fetch_operational_plan(frm).then((data) => {
		if (!data) return;
		apply_operational_calendar(frm, data.calendar);
		apply_task_detail(frm, data);
		apply_workload_distribution(frm, data);
		apply_cashflow_distribution(frm, data);
		apply_sequencing(frm, data);
		render_op_calendar_matrix(frm, data.calendar);
		render_op_distribution_html_from_doc(frm);
		frm.dirty();
		frappe.show_alert({
			message: __("{0} task(s) planned over the window", [
				((data.distribution && data.distribution.rows) || []).length,
			]),
			indicator: "green",
		});
	});
}

function load_operational_schedule(frm) {
	fetch_operational_plan(frm).then((data) => {
		if (!data) return;
		apply_sequencing(frm, data);
		frm.dirty();
		frappe.show_alert({ message: __("Critical path built"), indicator: "green" });
	});
}

// ---------------------------------------------------------------------------
// Fills
// ---------------------------------------------------------------------------
function apply_operational_calendar(frm, calendar) {
	if (!calendar) return;

	frm.clear_table("holiday");
	(calendar.holiday_rows || []).forEach((h) => {
		const row = frm.add_child("holiday");
		row.day_type = h.day_type;
		row.holiday_name = h.holiday_name;
		row.from_date = h.from_date;
		row.to_date = h.to_date;
		row.total = h.total;
		row.month = h.month;
	});

	frm.clear_table("no");
	(calendar.working_days_rows || []).forEach((r) => {
		const row = frm.add_child("no");
		row.year = r.year;
		for (let m = 1; m <= 12; m++) {
			row[String(m)] = r[String(m)] || 0;
		}
	});

	frm.refresh_field("holiday");
	frm.refresh_field("no");

	if (frm.doc.start_date && frm.doc.end_date) {
		frm.set_value(
			"duration_in_days",
			frappe.datetime.get_day_diff(frm.doc.end_date, frm.doc.start_date) + 1
		);
	}
}

function apply_task_detail(frm, data) {
	const task_map = index_tasks(data.tasks);
	const rows = (data.distribution && data.distribution.rows) || [];

	frm.clear_table("operational_plan_detail");
	rows.forEach((r) => {
		const t = task_map[r.task_id] || {};
		const rate = flt(r.unit_rate);
		const child = frm.add_child("operational_plan_detail");
		child.activity = r.task_id;
		child.activity_name = r.task_id;
		child.task_name = r.task_name;
		child.series = r.series;
		child.uom = r.uom;
		child.rate = rate;
		child.amount = flt(r.contract_qty) * rate;
		child.planned_amount = flt(r.distributed_qty) * rate;
		child.quantity = r.contract_qty;
		child.up_to_end_of_previous_year_executed = t.executed_qty;
		child.remaining_planned_qty = t.remaining_qty;
		child.planned = r.distributed_qty;
		child.revised_planneds = r.distributed_qty;
		child.this_year_executed = 0;
		child.duration = t.duration;
		child.planned_day = r.total_working_days;
		child.productivity = t.productivity;
		child.start_date = clip_date(t.start_date, frm.doc.start_date, frm.doc.end_date);
		child.end_date = clip_date(t.finish_date, frm.doc.start_date, frm.doc.end_date);
		child.to_date_executed = t.executed_qty;
		child.activity_physical_weight = t.activity_physical_weight;
	});
	frm.refresh_field("operational_plan_detail");
}

function apply_workload_distribution(frm, data) {
	const task_map = index_tasks(data.tasks);
	const cols = (data.distribution && data.distribution.columns) || [];
	const rows = (data.distribution && data.distribution.rows) || [];

	frm.clear_table("tasks_workload_distribution");
	rows.forEach((r) => {
		const t = task_map[r.task_id] || {};
		const child = frm.add_child("tasks_workload_distribution");
		child.activity = r.task_id;
		child.activity_name = r.task_id;
		child.task_name = r.task_name;
		child.series = r.series;
		child.uom = r.uom;
		child.start_date = clip_date(t.start_date, frm.doc.start_date, frm.doc.end_date);
		child.end_date = clip_date(t.finish_date, frm.doc.start_date, frm.doc.end_date);
		child.activity_physical_weight = t.activity_physical_weight;
		child.productivity = t.productivity;
		child.contract_qty = r.contract_qty;
		child.to_date_excuted_qty = t.executed_qty;
		child.total_remaining_qty = t.remaining_qty;
		child.planned_qty = r.distributed_qty;
		child.rate = r.unit_rate;
		cols.forEach((c) => {
			const field = OP_MONTHS[Number(String(c.key).slice(5, 7))];
			if (!field) return;
			const cell = (r.cells && r.cells[c.key]) || {};
			child[field] = cell.qty || 0;
			child[field + "_1"] = cell.percent || 0;
		});
	});
	frm.refresh_field("tasks_workload_distribution");
}

function apply_cashflow_distribution(frm, data) {
	const task_map = index_tasks(data.tasks);
	const cols = (data.distribution && data.distribution.columns) || [];
	const rows = (data.distribution && data.distribution.rows) || [];

	frm.clear_table("tasks_cashflow_distribution");
	rows.forEach((r) => {
		const t = task_map[r.task_id] || {};
		const rate = flt(r.unit_rate);
		const child = frm.add_child("tasks_cashflow_distribution");
		child.activity = r.task_id;
		child.activity_name = r.task_id;
		child.task_name = r.task_name;
		child.uom = r.uom;
		child.series = r.series;
		child.project = frm.doc.project;
		child.start_date = clip_date(t.start_date, frm.doc.start_date, frm.doc.end_date);
		child.end_date = clip_date(t.finish_date, frm.doc.start_date, frm.doc.end_date);
		child.rate = rate;
		child.contract_amount = flt(r.contract_qty) * rate;
		child.todate_executed_qty = t.executed_qty;
		child.total_remaining_qty = t.remaining_qty;
		child.this_year_revised_plan = r.distributed_qty;
		cols.forEach((c) => {
			const field = OP_MONTHS[Number(String(c.key).slice(5, 7))];
			if (!field) return;
			const cell = (r.cells && r.cells[c.key]) || {};
			child[field] = cell.amount || 0;
		});
	});
	frm.refresh_field("tasks_cashflow_distribution");
}

function apply_sequencing(frm, data) {
	frm.clear_table("activity_sequencing");
	(data.sequencing || []).forEach((s) => {
		const child = frm.add_child("activity_sequencing");
		Object.assign(child, s);
	});

	frm.clear_table("critical_path_table");
	(data.critical_path || []).forEach((c) => {
		const child = frm.add_child("critical_path_table");
		Object.assign(child, c);
	});

	frm.set_value("tasks_on_the_critical_path", data.tasks_on_critical_path || "");
	frm.set_value("critical_path_duration_in_days", String(data.critical_path_duration || ""));
	frm.set_value("critical_path_duration_in_day", String(data.critical_path_duration || ""));

	frm.refresh_field("activity_sequencing");
	frm.refresh_field("critical_path_table");
	render_op_gantt(frm);
}

// ---------------------------------------------------------------------------
// HTML views (same look as the Master Plan)
// ---------------------------------------------------------------------------
function render_op_calendar_html(frm, html) {
	const field = frm.get_field("op_calendar_html");
	if (field && field.$wrapper) field.$wrapper.html(html || "");
}

// Identical layout to the Master Plan's render_calendar_matrix.
function render_op_calendar_matrix(frm, data) {
	const field = frm.get_field("op_calendar_html");
	if (!field || !field.$wrapper) return;

	const months = (data && data.months) || [];
	if (!months.length) {
		render_op_calendar_html(
			frm,
			op_placeholder(__("No months in the selected year."))
		);
		return;
	}

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
			(g) =>
				`<th colspan="${g.count}" style="${MPC_TH}text-align:center">${esc(g.season || "")}</th>`
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
			(m) =>
				`<span style="color:var(--text-muted,#8d99a6);white-space:nowrap">${esc(m.label)}</span>`,
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

function restore_op_calendar_html(frm) {
	if (!frm.doc.holiday || !frm.doc.holiday.length) {
		render_op_calendar_html(
			frm,
			op_placeholder(__("Click '{0}' to load the working days calendar.", [
				__("Get Calender &  Working Days"),
			]))
		);
		return;
	}
	const holidays = frm.doc.holiday.map((h) => ({
		day_type: h.day_type || "Holiday",
		from_date: h.from_date,
		to_date: h.to_date || h.from_date,
	}));
	frappe
		.call({
			method: `${MASTER_NS}.recompute_working_days`,
			args: {
				holidays: holidays,
				country: "ET",
				weekly_off: frm.doc.weekly_off,
				start_date: frm.doc.start_date,
				end_date: frm.doc.end_date,
			},
		})
		.then((r) => {
			if (r.message) render_op_calendar_matrix(frm, r.message);
		});
}

// ---------------------------------------------------------------------------
// Critical path Gantt visualizer (drawn from the Critical Path Table)
// ---------------------------------------------------------------------------
function render_op_gantt(frm) {
	const field = frm.get_field("gantt_chart");
	if (!field || !field.$wrapper) return;

	const rows = (frm.doc.critical_path_table || []).filter((r) => r.es && r.ef);
	if (!rows.length) {
		field.$wrapper.html(
			op_placeholder(__("Click '{0}' to draw the Gantt chart.", [__("Get Critical Path")]))
		);
		return;
	}

	rows.sort(
		(a, b) => String(a.es).localeCompare(String(b.es)) || String(a.activity).localeCompare(String(b.activity))
	);

	const minDate = rows.reduce((m, r) => (!m || r.es < m ? r.es : m), rows[0].es);
	const maxDate = rows.reduce((m, r) => (!m || r.ef > m ? r.ef : m), rows[0].ef);
	const totalDays = Math.max(frappe.datetime.get_day_diff(maxDate, minDate) + 1, 1);
	const esc = frappe.utils.escape_html;
	const pct = (v) => Math.max(0, Math.min(100, v));

	const axisStart = frappe.datetime.str_to_obj(minDate);
	const axisEnd = frappe.datetime.str_to_obj(maxDate);
	const ticks = [];
	let d = new Date(axisStart.getFullYear(), axisStart.getMonth(), 1);
	while (d <= axisEnd && ticks.length < 60) {
		const off = frappe.datetime.get_day_diff(frappe.datetime.obj_to_str(d), minDate);
		if (off >= 0) {
			ticks.push({
				label: `${OP_MONTH_LABELS[d.getMonth()]} '${String(d.getFullYear()).slice(2)}`,
				left: pct((off / totalDays) * 100),
			});
		}
		d = new Date(d.getFullYear(), d.getMonth() + 1, 1);
	}
	const tickHtml = ticks
		.map(
			(t) =>
				`<div style="position:absolute;left:${t.left}%;transform:translateX(-50%);white-space:nowrap">${
					t.label
				}</div>`
		)
		.join("");

	const crit = rows.filter((r) => flt(r.free_float) <= 0).length;

	const bars = rows
		.map((r) => {
			const off = frappe.datetime.get_day_diff(r.es, minDate);
			const dur = Math.max(frappe.datetime.get_day_diff(r.ef, r.es) + 1, 1);
			const left = pct((off / totalDays) * 100);
			const width = Math.max((dur / totalDays) * 100, 0.4);
			const isCrit = flt(r.free_float) <= 0;
			const color = isCrit ? "#dc2626" : "#2563eb";
			const label = `${esc(r.task_id || r.activity || "")} &middot; ${esc(
				r.es
			)} &rarr; ${esc(r.ef)}${isCrit ? " &middot; " + __("critical") : ""}`;
			return (
				`<div style="display:flex;align-items:center;height:22px">` +
				`<div style="width:200px;min-width:200px;padding-right:8px;font-size:11px;` +
				`white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(
					r.task_id || r.activity || ""
				)}">${esc(r.task_id || r.activity || "")}</div>` +
				`<div style="flex:1;position:relative;height:16px;background:#f8fafc;border-left:1px solid #e2e8f0">` +
				`<div title="${label}" style="position:absolute;left:${left}%;width:${width}%;top:2px;` +
				`height:12px;border-radius:3px;background:${color};opacity:.85"></div></div></div>`
			);
		})
		.join("");

	field.$wrapper.html(
		`<div style="border:1px solid ${MPC_BORDER};border-radius:8px;overflow:hidden;margin:4px 0;` +
			`background:var(--fg-color,#fff)">` +
			`<div style="padding:8px 12px;background:${MPC_HEAD_BG};border-bottom:1px solid ${MPC_BORDER};` +
			`font-size:12px;color:var(--text-muted,#8d99a6)">` +
			`<b>${__("Critical Path Gantt")}</b> &middot; ${rows.length} ${__(
				"activities"
			)} &middot; <span style="color:#dc2626">${crit} ${__(
				"on the critical path"
			)}</span> &middot; ${esc(minDate)} &rarr; ${esc(maxDate)} ` +
			`&middot; <span style="color:#2563eb">${__("non-critical")}</span> / ` +
			`<span style="color:#dc2626">${__("critical")}</span></div>` +
			`<div style="padding:6px 12px;font-size:11px;color:var(--text-muted,#8d99a6);` +
			`position:relative;height:16px">` +
			`<div style="position:absolute;left:212px;right:12px;top:6px;height:14px">${tickHtml}</div>` +
			`</div>` +
			`<div style="overflow:auto;max-height:65vh;padding:4px 12px 10px">${bars}</div>` +
			`</div>`
	);
}

function render_op_distribution_html_from_doc(frm) {
	const rows = frm.doc.tasks_workload_distribution || [];
	if (!rows.length) {
		render_op_distribution_html(
			frm,
			op_placeholder(__("Click '{0}' to build the monthly distribution.", [
				__("Get Task Monthly Distribution"),
			]))
		);
		return;
	}
	render_op_distribution_html(frm, build_op_distribution_table(frm, rows));
}

function build_op_distribution_table(frm, rows) {
	const cols = op_month_columns(frm);
	const esc = frappe.utils.escape_html;

	if (!cols.length) return op_placeholder(__("No months in the selected window."));

	const head =
		`<tr><th rowspan="2" style="${OP_TH}text-align:left">${__("Item")}</th>` +
		`<th rowspan="2" style="${OP_TH}text-align:left">${__("Description")}</th>` +
		`<th rowspan="2" style="${OP_TH}">${__("Unit")}</th>` +
		`<th rowspan="2" style="${OP_TH}text-align:right">${__("Project Qty")}</th>` +
		cols
			.map(
				(c) =>
					`<th style="${OP_TH}white-space:nowrap">${esc(c.label)}</th>`
			)
			.join("") +
		`<th rowspan="2" style="${OP_TH}text-align:right">${__("TOTAL")}</th></tr>` +
		`<tr>${cols
			.map((c) => `<th style="${OP_TH}color:#64748b;font-weight:500">${c.month}</th>`)
			.join("")}</tr>`;

	let total_qty = 0;
	const col_total = cols.map(() => 0);

	const body = rows
		.map((r, i) => {
			const cells = cols
				.map((c, ci) => {
					const qty = flt(r[c.field]);
					col_total[ci] += qty;
					return `<td style="${OP_TD}text-align:right">${qty ? fmt_num(qty, 2) : ""}</td>`;
				})
				.join("");
			total_qty += flt(r.planned_qty);
			return (
				`<tr>` +
				`<td style="${OP_TD}color:#94a3b8">${esc(r.series || r.activity_name || i + 1)}</td>` +
				`<td style="${OP_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(
					r.task_name || ""
				)}">${esc(r.task_name || r.activity_name || "")}</td>` +
				`<td style="${OP_TD}white-space:nowrap">${esc(r.uom || "")}</td>` +
				`<td style="${OP_TD}text-align:right;font-weight:600">${fmt_num(r.contract_qty)}</td>` +
				cells +
				`<td style="${OP_TF}text-align:right">${fmt_num(r.planned_qty)}</td>` +
				`</tr>`
			);
		})
		.join("");

	const foot =
		`<tr><td colspan="4" style="${OP_TF}text-align:left">${__("Total")}</td>` +
		col_total
			.map((v) => `<td style="${OP_TF}text-align:right">${v ? fmt_num(v, 2) : ""}</td>`)
			.join("") +
		`<td style="${OP_TF}text-align:right">${fmt_num(total_qty)}</td></tr>`;

	return (
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
		'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
		`<b>${__("Workload Distribution")}</b> &middot; ${rows.length} ${__("items")} &middot; ${
			cols.length
		} ${__("months")}</div>` +
		'<div style="overflow:auto;max-height:70vh">' +
		`<table style="border-collapse:collapse;font-size:12px;width:100%"><thead>${head}</thead>` +
		`<tbody>${body}</tbody><tfoot>${foot}</tfoot></table>` +
		"</div></div>"
	);
}

function render_op_distribution_html(frm, html) {
	const field = frm.get_field("op_distribution_html");
	if (field && field.$wrapper) field.$wrapper.html(html || "");
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function op_month_columns(frm) {
	const cols = [];
	if (!frm.doc.start_date || !frm.doc.end_date) return cols;
	const s = frappe.datetime.str_to_obj(frm.doc.start_date);
	const e = frappe.datetime.str_to_obj(frm.doc.end_date);
	let d = new Date(s.getFullYear(), s.getMonth(), 1);
	const last = new Date(e.getFullYear(), e.getMonth(), 1);
	let guard = 0;
	while (d <= last && guard < 60) {
		cols.push({
			year: d.getFullYear(),
			month: d.getMonth() + 1,
			label: `${OP_MONTH_LABELS[d.getMonth()]},${d.getFullYear()}`,
			field: OP_MONTHS[d.getMonth() + 1],
		});
		d = new Date(d.getFullYear(), d.getMonth() + 1, 1);
		guard++;
	}
	return cols;
}

function index_tasks(tasks) {
	const map = {};
	(tasks || []).forEach((t) => {
		map[t.task_id] = t;
	});
	return map;
}

function clip_date(value, lo, hi) {
	if (!value) return value;
	let v = value;
	if (lo && v < lo) v = lo;
	if (hi && v > hi) v = hi;
	return v;
}

function fmt_num(value, dp) {
	dp = dp == null ? 2 : dp;
	const n = flt(value);
	if (!n) return "";
	return n.toLocaleString("en-US", { maximumFractionDigits: dp });
}

function op_placeholder(text) {
	return `<div style="border:1px dashed #cbd5e1;border-radius:10px;padding:12px 14px;color:#64748b;margin:4px 0">${frappe.utils.escape_html(
		text
	)}</div>`;
}
