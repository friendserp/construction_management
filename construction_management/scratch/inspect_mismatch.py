import frappe

def inspect():
	doc = frappe.get_doc('Stock Entry', 'SIV-2026-00005')
	print("STOCK ENTRY SIV-2026-00005 ITEMS:")
	for item in doc.items:
		item_code = item.item_code
		item_name = item.item_name
		item_group = item.item_group
		amount = item.amount
		sub_cat = frappe.db.get_value('Item', item_code, 'custom_subcategory')
		parent_ig = frappe.db.get_value('Item Group', item_group, 'parent_item_group')
		print(f"- Code: {item_code} | Name: {item_name} | Group: {item_group} | Parent Group: {parent_ig} | Subcategory: {sub_cat} | Amount: {amount}")
