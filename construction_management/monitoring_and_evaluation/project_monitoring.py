# Copyright (c) 2026, Friends ERP and contributors

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_project_monitoring_summary(project):
	latest_wap = frappe.get_all(
		"Weekly Action Plan",
		filters={"project": project, "docstatus": 1},
		fields=["name", "total_revenue", "total_cost", "projected_profit"],
		order_by="from_date desc",
		limit=1,
	)
	latest_wap = latest_wap[0] if latest_wap else None

	drr_totals = frappe.db.sql(
		"""
		SELECT
			SUM(COALESCE(total_cost, 0.0)) as actual_cost,
			SUM(COALESCE(revenue, 0.0)) as actual_revenue,
			SUM(COALESCE(profit_loss, 0.0)) as actual_profit,
			COUNT(*) as report_count
		FROM `tabDaily Resource Report`
		WHERE project = %s AND docstatus = 1
		""",
		(project,),
		as_dict=True,
	)

	totals = drr_totals[0] if drr_totals else {}

	return {
		"latest_weekly_plan": latest_wap.get("name") if latest_wap else None,
		"planned_revenue": flt(latest_wap.get("total_revenue")) if latest_wap else 0,
		"planned_cost": flt(latest_wap.get("total_cost")) if latest_wap else 0,
		"planned_profit": flt(latest_wap.get("projected_profit")) if latest_wap else 0,
		"actual_cost": flt(totals.get("actual_cost")),
		"actual_revenue": flt(totals.get("actual_revenue")),
		"actual_profit": flt(totals.get("actual_profit")),
		"daily_report_count": totals.get("report_count") or 0,
	}
