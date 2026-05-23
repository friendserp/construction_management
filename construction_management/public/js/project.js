frappe.ui.form.on('Project', {
	refresh: function(frm) {
		if (frm.doc.project_template && !frm.is_new()) {
			frm.add_custom_button(__('Update from Template'), function() {
				frappe.confirm(
					__('Are you sure you want to update all project tasks from the template? This will overwrite existing cost/unit values and create any missing tasks.'),
					function() {
						frappe.call({
							method: 'construction_management.task_hooks.update_project_tasks_from_template',
							args: {
								project_name: frm.doc.name
							},
							freeze: true,
							freeze_message: __('Updating tasks from template...'),
							callback: function(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __('Tasks updated successfully!'),
										indicator: 'green'
									});
									frm.reload_doc();
								}
							}
						});
					}
				);
			}, __('Actions'));
		}
	}
});
