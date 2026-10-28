// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

const NS =
	"construction_management.construction_management.doctype.monthly_plan.monthly_plan";

const MP_MONTH_LABELS = [
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

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_TYPE_RANK = { Sunday: 4, Holiday: 3, "Rainy Day": 2, "Holiday Leave": 1 };

// Same style tokens the Master / Operational Plan use.
const MPC_BORDER = "var(--border-color,#d1d8dd)";
const MPC_HEAD_BG = "var(--subtle-fg,#f4f5f6)";
const MPC_TH = `padding:6px 8px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);`;
const MPC_LABEL = `padding:6px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);white-space:nowrap;text-align:left;`;
const MPC_TD = `padding:5px 8px;border:1px solid ${MPC_BORDER};color:var(--text-color,#1f272e);`;
const MPC_TOTAL = `padding:5px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:700;text-align:right;`;
const DIS_TH = `padding:6px 8px;border:1px solid #e2e8f0;background:#f1f5f9;font-weight:600;text-align:center;`;
const DIS_TD = "padding:4px 6px;border:1px solid #eef2f7;white-space:nowrap;";
const DIS_TF = "padding:5px 6px;border:1px solid #e2e8f0;background:#f8fafc;font-weight:600;";

const DETAIL_FIELDS = [
	"activity",
	"activity_name",
	"uom",
	"rate",
	"amount",
	"planned_amount",
	"quantity",
	"up_to_end_of_previous_month_executed",
	"remaining_planned_qty",
	"planned",
	"this_month_executed",
	"duration",
	"planned_day",
	"productivity",
	"start_date",
	"end_date",
	"to_date_executed",
];

const WORKLOAD_FIELDS = [
	"task_id",
	"task_name",
	"uom",
	"quantity",
	"planned",
	"start_date",
	"end_date",
	"rate",
	"amount",
	"planned_amount",
].concat(Array.from({ length: 5 }, (_, i) => `week_${i + 1}`));

frappe.ui.form.on("Monthly Plan", {
	operational_plan(frm) {
		prefill_from_operational(frm);
	},
	month(frm) {
		apply_month_dates(frm, true);
	},
	refresh(frm) {
		load_op_months(frm).then(() => {
			if (!frm.doc.operational_plan) {
				frm.dashboard.set_headline(
					__("Select an Operational Plan, choose a Month, then the plan loads automatically.")
				);
				render_placeholder(frm, "mp_calendar_html", __("Select an Operational Plan first."));
				render_placeholder(frm, "mp_distribution_html", __("Select an Operational Plan first."));
				return;
			}
			if (!frm.doc.start_date || !frm.doc.end_date) {
				frm.dashboard.set_headline(__("Choose a Month to fill the Start / End dates."));
				render_placeholder(frm, "mp_calendar_html", __("Choose a Month."));
				render_placeholder(frm, "mp_distribution_html", __("Choose a Month."));
				return;
			}
			frm.dashboard.set_headline(
				__("Operational Plan: {0} · {1} → {2}", [
					frm.doc.operational_plan,
					frm.doc.start_date,
					frm.doc.end_date,
				])
			);
			// HTML fields are not persisted: rebuild the previews from the saved data.
			render_mp_calendar_matrix(frm);
			render_mp_distribution(frm);
		});
	},
	get_weekly_distribution(frm) {
		load_monthly_plan(frm);
	},
	add_to_holidays(frm) {
		load_monthly_calendar(frm);
	},
});

function prefill_from_operational(frm) {
	if (!frm.doc.operational_plan) return;
	frappe.db.get_doc("Operational Plan", frm.doc.operational_plan).then((op) => {
		const updates = {};
		if (op.project) updates.project = op.project;
		if (op.consultant) updates.consultant = op.consultant;
		if (op.client) updates.client = op.client;
		if (op.master_plan_name) updates.master_plan = op.master_plan_name;
		if (op.weekly_off) updates.weekly_off = op.weekly_off;
		if (Object.keys(updates).length) frm.set_value(updates);

		load_op_months(frm, op).then((months) => {
			if (!months.length) return;
			const now = new Date();
			const pick =
				months.find((m) => m.year === now.getFullYear() && m.month === now.getMonth() + 1) ||
				months[0];
			const unchanged = String(frm.doc.month || "") === pick.value;
			frm.set_value("month", pick.value);
			if (unchanged) apply_month_dates(frm, true);
		});
	});
}

// Months the Operational Plan spans, each clipped to the plan window.
function op_months(doc) {
	const out = [];
	if (!doc || !doc.start_date || !doc.end_date) return out;
	const s = frappe.datetime.str_to_obj(doc.start_date);
	const e = frappe.datetime.str_to_obj(doc.end_date);
	let d = new Date(s.getFullYear(), s.getMonth(), 1);
	const last = new Date(e.getFullYear(), e.getMonth(), 1);
	let guard = 0;
	while (d <= last && guard < 60) {
		const y = d.getFullYear();
		const m = d.getMonth() + 1;
		const from = frappe.datetime.obj_to_str(new Date(y, m - 1, 1)).slice(0, 10);
		const to = frappe.datetime.obj_to_str(new Date(y, m, 0)).slice(0, 10);
		out.push({
			value: MP_MONTH_LABELS[m - 1],
			year: y,
			month: m,
			start_date: from < doc.start_date ? doc.start_date : from,
			end_date: to > doc.end_date ? doc.end_date : to,
		});
		d = new Date(y, m, 1);
		guard++;
	}
	return out;
}

function load_op_months(frm, doc) {
	if (!frm.doc.operational_plan) {
		frm.set_df_property("month", "options", "");
		frm.__mp_months = [];
		return Promise.resolve([]);
	}
	const p = doc ? Promise.resolve(doc) : frappe.db.get_doc("Operational Plan", frm.doc.operational_plan);
	return p.then((op) => {
		const months = op_months(op);
		frm.__mp_months = months;
		frm.set_df_property("month", "options", months.map((m) => m.value).join("\n"));
		frm.refresh_field("month");
		return months;
	});
}

function apply_month_dates(frm, auto_load) {
	if (!frm.doc.month) return;
	const months = frm.__mp_months || [];
	const m = months.find((x) => x.value === String(frm.doc.month));
	if (!m) return;
	if (frm.doc.start_date !== m.start_date) frm.set_value("start_date", m.start_date);
	if (frm.doc.end_date !== m.end_date) frm.set_value("end_date", m.end_date);
	if (auto_load) load_monthly_plan(frm);
}

function fetch_monthly_plan(frm) {
	if (!frm.doc.operational_plan) {
		frappe.msgprint(__("Please select an Operational Plan first."));
		return Promise.resolve(null);
	}
	if (!frm.doc.start_date || !frm.doc.end_date) {
		frappe.msgprint(__("Please set the Start Date and End Date."));
		return Promise.resolve(null);
	}
	return frappe
		.call({
			method: `${NS}.get_monthly_plan_data`,
			args: {
				operational_plan: frm.doc.operational_plan,
				start_date: frm.doc.start_date,
				end_date: frm.doc.end_date,
			},
			freeze: true,
			freeze_message: __("Building the monthly plan from the Operational Plan..."),
		})
		.then((r) => r.message || null);
}

function load_monthly_calendar(frm) {
	fetch_monthly_plan(frm).then((data) => {
		if (!data) return;
		apply_monthly_calendar(frm, data.calendar);
		render_mp_calendar_matrix(frm);
		frm.dirty();
		frappe.show_alert({
			message: __("Working days loaded: {0}", [
				flt((data.calendar && data.calendar.total_working_days) || 0),
			]),
			indicator: "green",
		});
	});
}

function load_monthly_plan(frm) {
	fetch_monthly_plan(frm).then((data) => {
		if (!data) return;
		apply_monthly_calendar(frm, data.calendar);
		fill_table(frm, "monthly_plan_detail", data.detail, DETAIL_FIELDS);
		fill_table(frm, "weekly_task_workload", data.workload, WORKLOAD_FIELDS);
		fill_table(frm, "weekly_task_cashflow", data.cashflow, WORKLOAD_FIELDS);
		render_mp_calendar_matrix(frm);
		render_mp_distribution(frm);
		frm.dirty();
		frappe.show_alert({
			message: __("{0} task(s) planned for this month", [(data.detail || []).length]),
			indicator: "green",
		});
	});
}

function apply_monthly_calendar(frm, calendar) {
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
	frm.refresh_field("holiday");
}

function fill_table(frm, table, rows, fields) {
	frm.clear_table(table);
	(rows || []).forEach((r) => {
		const child = frm.add_child(table);
		fields.forEach((f) => {
			if (r[f] !== undefined && r[f] !== null) child[f] = r[f];
		});
	});
	frm.refresh_field(table);
}

// ---------------------------------------------------------------------------
// Working calendar matrix (same look as the Master Plan)
// ---------------------------------------------------------------------------
function render_placeholder(frm, fieldname, text) {
	const field = frm.get_field(fieldname);
	if (field && field.$wrapper) field.$wrapper.html(placeholder_html(text));
}

function render_mp_calendar_matrix(frm) {
	const field = frm.get_field("mp_calendar_html");
	if (!field || !field.$wrapper) return;

	if (!frm.doc.start_date || !frm.doc.end_date) {
		render_placeholder(frm, "mp_calendar_html", __("Choose a Month."));
		return;
	}

	const weeks = period_weeks(frm.doc.start_date, frm.doc.end_date);
	if (!weeks.length) {
		render_placeholder(frm, "mp_calendar_html", __("No weeks in the selected window."));
		return;
	}

	const types = day_type_map(frm.doc.holiday);
	const esc = frappe.utils.escape_html;

	const head =
		`<th style="${MPC_TH}text-align:left">${__("Week")}</th>` +
		weeks
			.map(
				(w) =>
					`<th style="${MPC_TH}text-align:center;min-width:90px">${__("Week")} ${
						w.index
					}<div style="font-size:10px;color:var(--text-muted,#8d99a6);font-weight:400">${esc(
						w.start
					)} &rarr; ${esc(w.end)}</div></th>`
			)
			.join("") +
		`<th style="${MPC_TH}text-align:right">${__("TOTAL")}</th>`;

	const count = (w, fn) => w.days.reduce((s, d) => s + fn(d), 0);

	const rowHtml = (label, fn, opts = {}) => {
		let total = 0;
		const cells = weeks
			.map((w) => {
				const v = fn(w);
				if (v) total += v;
				return `<td style="${MPC_TD}text-align:center;${
					opts.cellStyle || ""
				}">${v || ""}</td>`;
			})
			.join("");
		return (
			`<tr><td style="${MPC_LABEL}">${esc(label)}</td>${cells}` +
			`<td style="${MPC_TOTAL}${opts.totalStyle || ""}">${total || ""}</td></tr>`
		);
	};

	const isType = (w, t) => count(w, (d) => (types[d.date] === t ? 1 : 0));

	const rowsHtml =
		rowHtml(__("Calendar Days"), (w) => w.days.length) +
		rowHtml(__("Expected Rainy Days"), (w) => isType(w, "Rainy Day")) +
		rowHtml(__("Holidays"), (w) => isType(w, "Holiday")) +
		rowHtml(__("Holiday Leave Days"), (w) => isType(w, "Holiday Leave")) +
		rowHtml(__("Sundays"), (w) => isType(w, "Sunday")) +
		rowHtml(
			__("Available (Working) Days"),
			(w) => count(w, (d) => (types[d.date] ? 0 : 1)),
			{ cellStyle: "color:#0a7d33;font-weight:600", totalStyle: "color:#0a7d33" }
		);

	field.$wrapper.html(
		`<div style="border:1px solid ${MPC_BORDER};border-radius:8px;overflow:hidden;margin:4px 0;` +
			`background:var(--fg-color,#fff)">` +
			`<div style="padding:8px 12px;background:${MPC_HEAD_BG};border-bottom:1px solid ${MPC_BORDER};` +
			`font-size:12px;color:var(--text-muted,#8d99a6)">` +
			`<b>${__("Working Calendar")}</b> &middot; ${esc(frm.doc.start_date)} &rarr; ${esc(
				frm.doc.end_date
			)} &middot; ${__("Weekly Off")}: ${esc(frm.doc.weekly_off || "Sunday")}</div>` +
			`<div style="overflow:auto;max-height:70vh">` +
			`<table style="border-collapse:collapse;font-size:12px;width:100%">` +
			`<thead><tr>${head}</tr></thead><tbody>${rowsHtml}</tbody>` +
			`</table></div></div>`
	);
}

// ---------------------------------------------------------------------------
// Distribution (tasks as rows, weeks as columns) - quantity + cashflow
// ---------------------------------------------------------------------------
function render_mp_distribution(frm) {
	const field = frm.get_field("mp_distribution_html");
	if (!field || !field.$wrapper) return;

	const workload = frm.doc.weekly_task_workload || [];
	const cashflow = frm.doc.weekly_task_cashflow || [];
	if (!frm.doc.start_date || !frm.doc.end_date || (!workload.length && !cashflow.length)) {
		render_placeholder(
			frm,
			"mp_distribution_html",
			__("Click '{0}' to build the distribution.", [__("Get Weekly Distribution")])
		);
		return;
	}

	const weeks = period_weeks(frm.doc.start_date, frm.doc.end_date);
	const parts = [];
	if (workload.length) {
		parts.push(
			build_dist_table(workload, weeks, {
				title: __("Weekly Workload Distribution"),
				project_label: __("Project Qty"),
				project_val: (r) => flt(r.quantity),
				total_val: (r) => flt(r.planned),
			})
		);
	}
	if (cashflow.length) {
		parts.push(
			build_dist_table(cashflow, weeks, {
				title: __("Weekly Cashflow Distribution"),
				project_label: __("Project Amount"),
				project_val: (r) => flt(r.amount),
				total_val: (r) => flt(r.planned_amount),
			})
		);
	}
	field.$wrapper.html(parts.join(""));
}

function build_dist_table(rows, weeks, opts) {
	const esc = frappe.utils.escape_html;

	const head =
		`<tr><th rowspan="2" style="${DIS_TH}text-align:left">${__("Item")}</th>` +
		`<th rowspan="2" style="${DIS_TH}text-align:left">${__("Description")}</th>` +
		`<th rowspan="2" style="${DIS_TH}">${__("Unit")}</th>` +
		`<th rowspan="2" style="${DIS_TH}text-align:right">${opts.project_label}</th>` +
		weeks
			.map((w) => `<th style="${DIS_TH}min-width:90px">${__("Week")} ${w.index}</th>`)
			.join("") +
		`<th rowspan="2" style="${DIS_TH}text-align:right">${__("TOTAL")}</th></tr>` +
		`<tr>${weeks
			.map(
				(w) =>
					`<th style="${DIS_TH}color:#64748b;font-weight:400;font-size:10px">${esc(
						w.start
					)} &rarr; ${esc(w.end)}</th>`
			)
			.join("")}</tr>`;

	let total = 0;
	const col_total = weeks.map(() => 0);

	const body = rows
		.map((r, i) => {
			const cells = weeks
				.map((w, ci) => {
					const v = flt(r[`week_${w.index}`]);
					col_total[ci] += v;
					return `<td style="${DIS_TD}text-align:right">${v ? fmt_num(v, 2) : ""}</td>`;
				})
				.join("");
			total += opts.total_val(r);
			return (
				`<tr>` +
				`<td style="${DIS_TD}color:#94a3b8">${esc(r.task_id || i + 1)}</td>` +
				`<td style="${DIS_TD}max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(
					r.task_name || ""
				)}">${esc(r.task_name || "")}</td>` +
				`<td style="${DIS_TD}white-space:nowrap">${esc(r.uom || "")}</td>` +
				`<td style="${DIS_TD}text-align:right;font-weight:600">${fmt_num(opts.project_val(r))}</td>` +
				cells +
				`<td style="${DIS_TF}text-align:right">${fmt_num(opts.total_val(r))}</td>` +
				`</tr>`
			);
		})
		.join("");

	const foot =
		`<tr><td colspan="4" style="${DIS_TF}text-align:left">${__("Total")}</td>` +
		col_total
			.map((v) => `<td style="${DIS_TF}text-align:right">${v ? fmt_num(v, 2) : ""}</td>`)
			.join("") +
		`<td style="${DIS_TF}text-align:right">${fmt_num(total)}</td></tr>`;

	return (
		'<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin:4px 0">' +
		'<div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px">' +
		`<b>${opts.title}</b> &middot; ${rows.length} ${__("items")} &middot; ${weeks.length} ${__(
			"weeks"
		)}</div>` +
		'<div style="overflow:auto;max-height:70vh">' +
		`<table style="border-collapse:collapse;font-size:12px;width:100%"><thead>${head}</thead>` +
		`<tbody>${body}</tbody><tfoot>${foot}</tfoot></table>` +
		"</div></div>"
	);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function period_days(start, end) {
	const out = [];
	if (!start || !end) return out;
	let cur = frappe.datetime.str_to_obj(start);
	const last = frappe.datetime.str_to_obj(end);
	let guard = 0;
	while (cur <= last && guard < 400) {
		out.push({
			date: frappe.datetime.obj_to_str(cur).slice(0, 10),
			day: cur.getDate(),
			weekday: cur.getDay(),
		});
		cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1);
		guard++;
	}
	return out;
}

// Group the window's days into 7-day blocks (Week 1 = start .. start+6, ...).
function period_weeks(start, end) {
	const days = period_days(start, end);
	const weeks = [];
	for (let i = 0; i < days.length; i += 7) {
		const chunk = days.slice(i, i + 7);
		weeks.push({
			index: weeks.length + 1,
			days: chunk,
			start: chunk[0].date,
			end: chunk[chunk.length - 1].date,
		});
	}
	return weeks;
}

// Expand the holiday grid into a date -> type map (Sunday > Holiday > Rainy > Leave).
function day_type_map(holiday_rows) {
	const map = {};
	(holiday_rows || []).forEach((h) => {
		if (!h.from_date) return;
		const type = DAY_TYPE_RANK[h.day_type] ? h.day_type : "Holiday";
		let from = h.from_date;
		let to = h.to_date || h.from_date;
		if (to < from) {
			const t = from;
			from = to;
			to = t;
		}
		let cur = from;
		let guard = 0;
		while (cur <= to && guard < 400) {
			if (!map[cur] || (DAY_TYPE_RANK[type] || 0) > (DAY_TYPE_RANK[map[cur]] || 0)) {
				map[cur] = type;
			}
			cur = frappe.datetime.add_days(cur, 1);
			guard++;
		}
	});
	return map;
}

function placeholder_html(text) {
	return `<div style="border:1px dashed #cbd5e1;border-radius:10px;padding:12px 14px;color:#64748b;margin:4px 0">${frappe.utils.escape_html(
		text
	)}</div>`;
}

function fmt_num(value, dp) {
	dp = dp == null ? 2 : dp;
	const n = flt(value);
	if (!n) return "";
	return n.toLocaleString("en-US", { maximumFractionDigits: dp });
}
