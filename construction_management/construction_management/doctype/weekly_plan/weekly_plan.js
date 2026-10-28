// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

const NS =
	"construction_management.construction_management.doctype.weekly_plan.weekly_plan";

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_TYPE_RANK = { Sunday: 4, Holiday: 3, "Rainy Day": 2, "Holiday Leave": 1 };

const MPC_BORDER = "var(--border-color,#d1d8dd)";
const MPC_HEAD_BG = "var(--subtle-fg,#f4f5f6)";
const MPC_TH = `padding:6px 8px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);`;
const MPC_LABEL = `padding:6px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:600;color:var(--text-color,#1f272e);white-space:nowrap;text-align:left;`;
const MPC_TD = `padding:5px 8px;border:1px solid ${MPC_BORDER};color:var(--text-color,#1f272e);`;
const MPC_TOTAL = `padding:5px 10px;border:1px solid ${MPC_BORDER};background:${MPC_HEAD_BG};font-weight:700;text-align:right;`;
const DIS_TH = `padding:6px 8px;border:1px solid #e2e8f0;background:#f1f5f9;font-weight:600;text-align:center;`;
const DIS_TD = "padding:4px 6px;border:1px solid #eef2f7;white-space:nowrap;";
const DIS_TF = "padding:5px 6px;border:1px solid #e2e8f0;background:#f8fafc;font-weight:600;";

const WEEK_DETAIL_FIELDS = [
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

const DAILY_WORKLOAD_FIELDS = [
	"task_id",
	"uom",
	"task_name",
	"planned",
	"start_date",
	"end_date",
	"rate",
].concat(Array.from({ length: 7 }, (_, i) => `day_${i + 1}`));

const DAILY_CASHFLOW_FIELDS = [
	"task_id",
	"task_name",
	"planned_amount",
	"uom",
	"start_date",
	"end_date",
].concat(Array.from({ length: 7 }, (_, i) => `day_${i + 1}`));

frappe.ui.form.on("Weekly Plan", {
	monthly_plan(frm) {
		prefill_from_monthly(frm);
	},
	week(frm) {
		apply_week_dates(frm, true);
	},
	refresh(frm) {
		load_mp_weeks(frm).then(() => {
			if (!frm.doc.monthly_plan) {
				frm.dashboard.set_headline(
					__("Select a Monthly Plan, choose a Week, then the plan loads automatically.")
				);
				render_placeholder(frm, "wp_calendar_html", __("Select a Monthly Plan first."));
				render_placeholder(frm, "wp_distribution_html", __("Select a Monthly Plan first."));
				return;
			}
			if (!frm.doc.start_date || !frm.doc.end_date) {
				frm.dashboard.set_headline(__("Choose a Week to fill the Start / End dates."));
				render_placeholder(frm, "wp_calendar_html", __("Choose a Week."));
				render_placeholder(frm, "wp_distribution_html", __("Choose a Week."));
				return;
			}
			frm.dashboard.set_headline(
				__("Monthly Plan: {0} · {1} → {2}", [
					frm.doc.monthly_plan,
					frm.doc.start_date,
					frm.doc.end_date,
				])
			);
			// HTML fields are not persisted: rebuild the previews from the saved data.
			render_wp_calendar_matrix(frm);
			render_wp_distribution(frm);
		});
	},
	get_daily_distribution(frm) {
		load_weekly_plan(frm);
	},
});

function prefill_from_monthly(frm) {
	if (!frm.doc.monthly_plan) return;
	frappe.db.get_doc("Monthly Plan", frm.doc.monthly_plan).then((mp) => {
		const updates = {};
		if (mp.project) updates.project = mp.project;
		if (mp.consultant) updates.consultant = mp.consultant;
		if (mp.client) updates.client = mp.client;
		if (mp.operational_plan) updates.op_name = mp.operational_plan;
		updates.start_date = mp.start_date;
		updates.end_date = mp.end_date;
		frm.set_value(updates);

		load_mp_weeks(frm, mp).then((weeks) => {
			if (!weeks.length) return;
			const pick = weeks[0];
			const unchanged = String(frm.doc.week || "") === pick.value;
			frm.set_value("week", pick.value);
			if (unchanged) apply_week_dates(frm, true);
		});
	});
}

// Seven day blocks inside the Monthly Plan window.
function mp_weeks(doc) {
	const out = [];
	if (!doc || !doc.start_date || !doc.end_date) return out;
	const total = frappe.datetime.get_day_diff(doc.end_date, doc.start_date) + 1;
	const nWeeks = Math.max(1, Math.ceil(total / 7));
	for (let i = 0; i < nWeeks; i++) {
		const from = frappe.datetime.add_days(doc.start_date, i * 7);
		let to = frappe.datetime.add_days(doc.start_date, i * 7 + 6);
		if (to > doc.end_date) to = doc.end_date;
		out.push({ value: `Week ${i + 1}`, start_date: from, end_date: to });
	}
	return out;
}

function load_mp_weeks(frm, doc) {
	if (!frm.doc.monthly_plan) {
		frm.set_df_property("week", "options", "");
		frm.__mp_weeks = [];
		return Promise.resolve([]);
	}
	const p = doc ? Promise.resolve(doc) : frappe.db.get_doc("Monthly Plan", frm.doc.monthly_plan);
	return p.then((mp) => {
		const weeks = mp_weeks(mp);
		frm.__mp_weeks = weeks;
		frm.set_df_property("week", "options", weeks.map((w) => w.value).join("\n"));
		frm.refresh_field("week");
		return weeks;
	});
}

function apply_week_dates(frm, auto_load) {
	if (!frm.doc.week) return;
	const weeks = frm.__mp_weeks || [];
	const w = weeks.find((x) => x.value === String(frm.doc.week));
	if (!w) return;
	if (frm.doc.start_date !== w.start_date) frm.set_value("start_date", w.start_date);
	if (frm.doc.end_date !== w.end_date) frm.set_value("end_date", w.end_date);
	if (auto_load) load_weekly_plan(frm);
}

function fetch_weekly_plan(frm) {
	if (!frm.doc.monthly_plan) {
		frappe.msgprint(__("Please select a Monthly Plan first."));
		return Promise.resolve(null);
	}
	if (!frm.doc.start_date || !frm.doc.end_date) {
		frappe.msgprint(__("Please set the Start Date and End Date."));
		return Promise.resolve(null);
	}
	return frappe
		.call({
			method: `${NS}.get_weekly_plan_data`,
			args: {
				monthly_plan: frm.doc.monthly_plan,
				start_date: frm.doc.start_date,
				end_date: frm.doc.end_date,
			},
			freeze: true,
			freeze_message: __("Splitting the week into days from the Monthly Plan..."),
		})
		.then((r) => r.message || null);
}

function load_weekly_plan(frm) {
	fetch_weekly_plan(frm).then((data) => {
		if (!data) return;
		apply_weekly_calendar(frm, data.calendar);
		fill_table(frm, "weekly_plan_detail", data.detail, WEEK_DETAIL_FIELDS);
		fill_table(frm, "daily_task_workload", data.workload, DAILY_WORKLOAD_FIELDS);
		fill_table(frm, "daily_task_cashflow", data.cashflow, DAILY_CASHFLOW_FIELDS);
		render_wp_calendar_matrix(frm);
		render_wp_distribution(frm);
		frm.dirty();
		frappe.show_alert({
			message: __("{0} task(s) planned for this week", [(data.detail || []).length]),
			indicator: "green",
		});
	});
}

function apply_weekly_calendar(frm, calendar) {
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

function render_wp_calendar_matrix(frm) {
	const field = frm.get_field("wp_calendar_html");
	if (!field || !field.$wrapper) return;

	if (!frm.doc.start_date || !frm.doc.end_date) {
		render_placeholder(frm, "wp_calendar_html", __("Choose a Week."));
		return;
	}

	const days = period_days(frm.doc.start_date, frm.doc.end_date);
	if (!days.length) {
		render_placeholder(frm, "wp_calendar_html", __("No days in the selected window."));
		return;
	}

	const types = day_type_map(frm.doc.holiday);
	const esc = frappe.utils.escape_html;

	const head =
		`<th style="${MPC_TH}text-align:left">${__("Day")}</th>` +
		days
			.map(
				(d) =>
					`<th style="${MPC_TH}text-align:center;min-width:60px">${d.day} ${esc(
						d.date
					)}<div style="font-size:10px;color:var(--text-muted,#8d99a6);font-weight:400">${
						WEEKDAY_LABELS[d.weekday]
					}</div></th>`
			)
			.join("") +
		`<th style="${MPC_TH}text-align:right">${__("TOTAL")}</th>`;

	const rowHtml = (label, fn, opts = {}) => {
		let total = 0;
		const cells = days
			.map((d) => {
				const v = fn(d);
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

	const isType = (d, t) => (types[d.date] === t ? 1 : 0);

	const rowsHtml =
		rowHtml(__("Calendar Days"), () => 1) +
		rowHtml(__("Expected Rainy Days"), (d) => isType(d, "Rainy Day")) +
		rowHtml(__("Holidays"), (d) => isType(d, "Holiday")) +
		rowHtml(__("Holiday Leave Days"), (d) => isType(d, "Holiday Leave")) +
		rowHtml(__("Sundays"), (d) => isType(d, "Sunday")) +
		rowHtml(
			__("Available (Working) Days"),
			(d) => (types[d.date] ? 0 : 1),
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
			`<div style="overflow:auto">` +
			`<table style="border-collapse:collapse;font-size:12px;width:100%">` +
			`<thead><tr>${head}</tr></thead><tbody>${rowsHtml}</tbody>` +
			`</table></div></div>`
	);
}

// ---------------------------------------------------------------------------
// Daily distribution (tasks as rows, days as columns) - quantity + cashflow
// ---------------------------------------------------------------------------
function render_wp_distribution(frm) {
	const field = frm.get_field("wp_distribution_html");
	if (!field || !field.$wrapper) return;

	const workload = frm.doc.daily_task_workload || [];
	const cashflow = frm.doc.daily_task_cashflow || [];
	if (!frm.doc.start_date || !frm.doc.end_date || (!workload.length && !cashflow.length)) {
		render_placeholder(
			frm,
			"wp_distribution_html",
			__("Click '{0}' to build the distribution.", [__("Get Daily Distribution")])
		);
		return;
	}

	const days = period_days(frm.doc.start_date, frm.doc.end_date);
	const qty_by_task = {};
	const amount_by_task = {};
	(frm.doc.weekly_plan_detail || []).forEach((d) => {
		qty_by_task[d.activity] = flt(d.quantity);
		amount_by_task[d.activity] = flt(d.planned_amount);
	});

	const parts = [];
	if (workload.length) {
		parts.push(
			build_day_dist_table(workload, days, {
				title: __("Daily Workload Distribution"),
				project_label: __("Project Qty"),
				project_val: (r) => flt(qty_by_task[r.task_id]),
				total_val: (r) => flt(r.planned),
			})
		);
	}
	if (cashflow.length) {
		parts.push(
			build_day_dist_table(cashflow, days, {
				title: __("Daily Cashflow Distribution"),
				project_label: __("Project Amount"),
				project_val: (r) => flt(amount_by_task[r.task_id]),
				total_val: (r) => flt(r.planned_amount),
			})
		);
	}
	field.$wrapper.html(parts.join(""));
}

function build_day_dist_table(rows, days, opts) {
	const esc = frappe.utils.escape_html;

	const head =
		`<tr><th rowspan="2" style="${DIS_TH}text-align:left">${__("Item")}</th>` +
		`<th rowspan="2" style="${DIS_TH}text-align:left">${__("Description")}</th>` +
		`<th rowspan="2" style="${DIS_TH}">${__("Unit")}</th>` +
		`<th rowspan="2" style="${DIS_TH}text-align:right">${opts.project_label}</th>` +
		days
			.map((d) => `<th style="${DIS_TH}min-width:60px">${d.day}</th>`)
			.join("") +
		`<th rowspan="2" style="${DIS_TH}text-align:right">${__("TOTAL")}</th></tr>` +
		`<tr>${days
			.map(
				(d) =>
					`<th style="${DIS_TH}color:#64748b;font-weight:400;font-size:10px">${
						WEEKDAY_LABELS[d.weekday]
					}</th>`
			)
			.join("")}</tr>`;

	let total = 0;
	const col_total = days.map(() => 0);

	const body = rows
		.map((r, i) => {
			const cells = days
				.map((d, ci) => {
					const v = flt(r[`day_${d.index}`]);
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
		`<b>${opts.title}</b> &middot; ${rows.length} ${__("items")} &middot; ${days.length} ${__(
			"days"
		)}</div>` +
		'<div style="overflow:auto">' +
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
			index: out.length + 1,
		});
		cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1);
		guard++;
	}
	return out;
}

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
