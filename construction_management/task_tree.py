import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_boq_tree_nodes(
	doctype="Task", parent=None, task=None, project=None, is_root=False, **kwargs
):
	"""Task tree nodes enriched with the BOQ columns shown in the tree view."""
	from erpnext.projects.doctype.task.task import get_children

	nodes = get_children(
		doctype, parent=parent, task=task, project=project, is_root=is_root
	)
	if not nodes:
		return []

	names = [node.get("value") for node in nodes if node.get("value")]
	detail_rows = frappe.get_all(
		"Task",
		filters={"name": ["in", names]},
		fields=[
			"name",
			"is_group",
			"custom_pay_item_no",
			"custom_unit_rate",
			"custom_contract_qty",
			"custom_unit",
			"cost_break_down",
		],
	)
	details = {row.name: row for row in detail_rows}

	cbd_direct = {}
	direct_names = [row.get("cost_break_down") for row in detail_rows if row.get("cost_break_down")]
	if direct_names:
		for row in frappe.get_all(
			"Cost Break Down",
			filters={"name": ["in", direct_names]},
			fields=["name", "total_unit_cost"],
		):
			cbd_direct[row.name] = row

	cbd_by_task = {}
	if names:
		for row in frappe.db.sql(
			"""
			SELECT c.task, c.name, c.total_unit_cost
			FROM `tabCost Break Down` c
			INNER JOIN (
				SELECT task, MAX(modified) AS modified
				FROM `tabCost Break Down`
				WHERE task IN %(names)s
				GROUP BY task
			) latest
				ON latest.task = c.task AND latest.modified = c.modified
			""",
			{"names": names},
			as_dict=True,
		):
			cbd_by_task[row.task] = row

	for node in nodes:
		name = node.get("value")
		detail = details.get(name) or frappe._dict()

		node["is_group"] = int(detail.get("is_group") or 0)
		node["pay_item_no"] = detail.get("custom_pay_item_no") or ""
		node["unit_rate"] = flt(detail.get("custom_unit_rate"))
		qty = detail.get("custom_contract_qty")
		node["qty"] = flt(qty) if qty is not None else None
		node["uom"] = detail.get("custom_unit") or ""

		linked = detail.get("cost_break_down")
		if linked and linked in cbd_direct:
			node["cbd"] = linked
			node["cbd_total_unit_cost"] = flt(cbd_direct[linked].get("total_unit_cost"))
		else:
			cbd = cbd_by_task.get(name) or frappe._dict()
			node["cbd"] = cbd.get("name")
			node["cbd_total_unit_cost"] = (
				flt(cbd.get("total_unit_cost")) if cbd.get("name") else None
			)

	return nodes

