# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe

def copy_fields_from_template(doc, method):
	"""
	Frappe before_insert hook on Task.
	Copies custom fields and specific standard fields from the prototype
	template task if this task is generated from one.
	"""
	if not doc.template_task:
		return

	try:
		template_doc = frappe.get_doc("Task", doc.template_task)
	except frappe.DoesNotExistError:
		# If the template task doesn't exist, exit gracefully
		return

	# 1. Copy Standard Fields that are not copied by default in ERPNext
	standard_fields = ["expected_time", "is_milestone"]
	for field in standard_fields:
		# If the template has a non-zero / non-empty value, copy it
		if template_doc.get(field):
			doc.set(field, template_doc.get(field))

	# 2. Copy all Custom Fields dynamically (defined as custom or starting with 'custom_')
	custom_fields = [f.fieldname for f in frappe.get_meta("Task").fields if getattr(f, "is_custom_field", None) or f.fieldname.startswith("custom_")]
	
	for fieldname in custom_fields:
		# Copy the value if it is populated (not None and not empty string) in the template task doc
		val = template_doc.get(fieldname)
		if val is not None and val != "":
			doc.set(fieldname, val)


@frappe.whitelist()
def update_project_tasks_from_template(project_name):
	project = frappe.get_doc("Project", project_name)
	if not project.project_template:
		frappe.throw(frappe._("Please select a Project Template first."))

	template = frappe.get_doc("Project Template", project.project_template)

	# 1. Fetch existing tasks
	existing_tasks = frappe.get_all(
		"Task",
		filters={"project": project.name},
		fields=["name", "template_task"]
	)
	existing_tasks_map = {t.template_task: t.name for t in existing_tasks if t.template_task}

	# 2. Get list of all Custom Fields on Task
	custom_fields = [f.fieldname for f in frappe.get_meta("Task").fields if getattr(f, "is_custom_field", None) or f.fieldname.startswith("custom_")]

	new_tasks_created = []
	tmp_task_details = []

	# Fields to sync from prototype task
	standard_fields_to_sync = ["expected_time", "is_milestone", "subject", "description", "task_weight", "type", "priority", "color"]

	for task in template.tasks:
		try:
			template_task_details = frappe.get_doc("Task", task.task)
		except frappe.DoesNotExistError:
			continue

		if task.task in existing_tasks_map:
			# Update existing task
			child_task = frappe.get_doc("Task", existing_tasks_map[task.task])
			
			# Sync Standard Fields
			for field in standard_fields_to_sync:
				# If the template value is different from child value, update it
				if template_task_details.get(field) != child_task.get(field):
					child_task.set(field, template_task_details.get(field))

			# Sync Custom Fields
			for fieldname in custom_fields:
				val = template_task_details.get(fieldname)
				if val is not None and val != child_task.get(fieldname):
					child_task.set(fieldname, val)

			child_task.save(ignore_permissions=True)
		else:
			# Create missing task
			new_task = frappe.get_doc(
				dict(
					doctype="Task",
					subject=template_task_details.subject,
					project=project.name,
					status="Open",
					exp_start_date=project.calculate_start_date(template_task_details),
					exp_end_date=project.calculate_end_date(template_task_details),
					description=template_task_details.description,
					task_weight=template_task_details.task_weight,
					type=template_task_details.type,
					issue=template_task_details.issue,
					is_group=template_task_details.is_group,
					color=template_task_details.color,
					template_task=template_task_details.name,
					priority=template_task_details.priority,
				)
			)

			# Copy custom fields to the new task
			for fieldname in custom_fields:
				val = template_task_details.get(fieldname)
				if val is not None:
					new_task.set(fieldname, val)

			# Copy other standard fields
			new_task.expected_time = template_task_details.expected_time
			new_task.is_milestone = template_task_details.is_milestone

			new_task.insert(ignore_permissions=True)
			new_tasks_created.append(new_task)
			tmp_task_details.append(template_task_details)

	# 3. Handle dependency mapping for new tasks if any
	if new_tasks_created:
		project.dependency_mapping(tmp_task_details, new_tasks_created)

	return True


def update_task_todate_values(doc, method):
	"""
	Hook for Timesheet on_submit and on_cancel.
	Updates 'custom_todate_exexuted_qty' and 'custom_todate_executed_amount' on Task.
	"""
	# Get all unique tasks mentioned in this Timesheet
	tasks = list(set([row.task for row in doc.time_logs if row.task]))
	if not tasks:
		return

	for task_name in tasks:
		# Recalculate sums of custom_todate_executed_qty and custom_todate_executed_amt
		# from all submitted Timesheet Details for this task
		results = frappe.db.sql("""
			SELECT 
				SUM(td.custom_todate_executed_qty) as total_qty,
				SUM(td.custom_todate_executed_amt) as total_amount
			FROM `tabTimesheet Detail` td
			INNER JOIN `tabTimesheet` t ON td.parent = t.name
			WHERE td.task = %s AND t.docstatus = 1
		""", (task_name,), as_dict=True)

		total_qty = results[0].total_qty or 0.0
		total_amount = results[0].total_amount or 0.0

		# Update the task
		frappe.db.set_value("Task", task_name, {
			"custom_todate_exexuted_qty": total_qty,
			"custom_todate_executed_amount": total_amount
		}, update_modified=True)


