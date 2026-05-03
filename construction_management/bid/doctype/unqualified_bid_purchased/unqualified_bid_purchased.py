import frappe
from frappe.model.document import Document

class UnqualifiedBidPurchased(Document):
	pass

@frappe.whitelist()
def get_bid_flow(doctype, docname):
	doc = frappe.get_doc(doctype, docname)
	flow = []
	
	# Current document
	flow.append({
		"label": doctype,
		"id": docname,
		"doctype": doctype,
		"icon": get_icon(doctype),
		"current": True
	})
	
	# Trace backwards
	current_doc = doc
	while True:
		parent_link = get_parent_link(current_doc)
		if not parent_link:
			break
		
		parent_doctype = parent_link["doctype"]
		parent_id = current_doc.get(parent_link["fieldname"])
		
		if not parent_id:
			break
			
		flow.insert(0, {
			"label": parent_doctype,
			"id": parent_id,
			"doctype": parent_doctype,
			"icon": get_icon(parent_doctype)
		})
		
		try:
			current_doc = frappe.get_doc(parent_doctype, parent_id)
		except frappe.DoesNotExistError:
			break
			
	return flow

def get_parent_link(doc):
	links = {
		"Unqualified Bid Purchased": {"fieldname": "bid_opening_followup_id", "doctype": "Bid Opening Followup"},
		"Bid Result": {"fieldname": "bid_opening_followup_id", "doctype": "Bid Opening Followup"},
		"None Responsive Bid": {"fieldname": "bid_opening_followup_id", "doctype": "Bid Opening Followup"},
		"Bid Opening Followup": {"fieldname": "bid_documentation_check_list", "doctype": "Bid Documentation Checklist"},
		"Bid Documentation Checklist": {"fieldname": "site_visit_assessment", "doctype": "Site Visit Assessment"},
		"Site Visit Assessment": {"fieldname": "bid_followup_id", "doctype": "Bid Followup"}
	}
	# Fallback/Additional links if Site Visit is skipped
	if doc.doctype == "Bid Documentation Checklist" and not doc.site_visit_assessment:
		return {"fieldname": "bid_followup_id", "doctype": "Bid Followup"}
		
	return links.get(doc.doctype)

def get_icon(doctype):
	icons = {
		"Bid Followup": "📝",
		"Site Visit Assessment": "📍",
		"Bid Documentation Checklist": "✓",
		"Bid Opening Followup": "🔓",
		"Unqualified Bid Purchased": "❌",
		"Bid Result": "🏆",
		"None Responsive Bid": "⚠️"
	}
	return icons.get(doctype, "📄")
