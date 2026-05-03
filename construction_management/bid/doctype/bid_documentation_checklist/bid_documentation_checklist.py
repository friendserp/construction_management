# Copyright (c) 2026, Friends ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BidDocumentationChecklist(Document):
	def on_submit(self):
		tp_filled = bool(self.get('tp'))
		fp_filled = bool(self.get('fp'))
		cbd_filled = bool(self.get('cbd'))
		
		all_checked = True
		if self.get('items'):
			for item in self.items:
				if not item.get('check'):
					all_checked = False
					break
		else:
			all_checked = False
		
		if tp_filled and fp_filled and cbd_filled and all_checked:
			self.db_set('status', 'Qualified')
		else:
			self.db_set('status', 'Un Qualified')