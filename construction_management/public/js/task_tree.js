frappe.provide("frappe.treeview_settings");

(function () {
	const settings = frappe.treeview_settings["Task"];
	if (!settings) {
		return;
	}

	settings.get_tree_nodes = "construction_management.task_tree.get_boq_tree_nodes";

	function get_currency() {
		return (frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "ETB";
	}

	function fmt_currency(value) {
		if (value === null || value === undefined || value === "") {
			return "";
		}
		return format_currency(value, get_currency());
	}

	function fmt_qty(value) {
		if (value === null || value === undefined || value === "") {
			return "";
		}
		return format_number(value, null, 2);
	}

	function cell(key, html, extra_class, title) {
		const title_attr = title
			? ` title="${frappe.utils.escape_html(title)}"`
			: "";
		return `<span class="boq-cell boq-cell-${key}${
			extra_class ? " " + extra_class : ""
		}"${title_attr}>${html || ""}</span>`;
	}

	settings.get_label = function (node) {
		const data = node.data || {};
		const esc = frappe.utils.escape_html;

		if (!data.value) {
			return esc(__(node.label || node.title || ""));
		}

		if (cint(data.is_group)) {
			return `<span class="boq-tree-row boq-tree-group">
				${cell("pay", esc(data.pay_item_no || ""))}
				${cell(
					"desc",
					`<strong>${esc(data.title || data.value)}</strong>`,
					"",
					data.title || data.value
				)}
				${cell("unit", "")}
				${cell("qty", "")}
				${cell("rate", "")}
				${cell("cbd", "")}
			</span>`;
		}

		const cbd = data.cbd
			? `<span class="boq-cbd-link" role="link" data-cbd="${esc(
					data.cbd
			  )}" title="${esc(fmt_currency(data.cbd_total_unit_cost))}">${esc(
					data.cbd
			  )}</span>`
			: "";

		return `<span class="boq-tree-row">
			${cell("pay", esc(data.pay_item_no || ""))}
			${cell("desc", esc(data.title || data.value), "", data.title || data.value)}
			${cell("unit", esc(data.uom || ""))}
			${cell("qty", fmt_qty(data.qty))}
			${cell("rate", fmt_currency(data.unit_rate))}
			${cell("cbd", cbd)}
		</span>`;
	};

	let styles_injected = false;

	function inject_styles() {
		if (styles_injected) {
			return;
		}
		styles_injected = true;

		const css = `
			.treeview .tree.tree-rows .tree-link > .tree-label {
				flex: 1 1 0%;
				min-width: 0;
				overflow: hidden;
				white-space: nowrap;
			}
			.boq-tree-row {
				display: flex;
				align-items: center;
				gap: 8px;
				width: 100%;
				min-width: 0;
			}
			.boq-cell {
				flex: 0 0 auto;
				overflow: hidden;
				text-overflow: ellipsis;
				white-space: nowrap;
			}
.boq-cell-desc {
			flex: 0 0 auto;
			width: 300px;
			min-width: 0;
			max-width: none;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
			padding-right: 8px;
		}
			.boq-cell-pay { width: 110px; }
			.boq-cell-unit {
				width: 70px;
				margin-left: auto;
			}
			.boq-cell-qty {
				width: 90px;
				text-align: right;
				font-variant-numeric: tabular-nums;
			}
			.boq-cell-rate {
				width: 110px;
				text-align: right;
				font-variant-numeric: tabular-nums;
			}
			.boq-cell-cbd {
				width: 130px;
				text-align: right;
			}
.boq-tree-header {
			display: flex;
			align-items: center;
			gap: 8px;
			padding: 6px 16px 6px 44px;
			font-size: var(--text-sm);
			font-weight: 600;
			color: var(--ink-gray-5);
			border-bottom: 1px solid var(--outline-gray-2);
			margin-bottom: 4px;
		}
		.boq-tree-header .boq-cell-desc {
			flex: 0 0 auto;
			width: 300px;
			padding-right: 8px;
		}
			.boq-cbd-link {
				text-decoration: underline;
				cursor: pointer;
				white-space: nowrap;
			}
			.boq-cbd-link:hover {
				color: var(--ink-gray-9);
			}
		`;

		$(`<style id="boq-task-tree-style">${css}</style>`).appendTo("head");
	}

	function add_header(treeview) {
		if (!treeview.body) {
			return;
		}

		const $body = $(treeview.body);
		$body.find(".boq-tree-header").remove();
		$body.prepend(`
			<div class="boq-tree-header">
				<span class="boq-cell boq-cell-pay">${__("Pay Item No")}</span>
				<span class="boq-cell boq-cell-desc">${__("Description")}</span>
				<span class="boq-cell boq-cell-unit">${__("Unit")}</span>
				<span class="boq-cell boq-cell-qty">${__("Qty")}</span>
				<span class="boq-cell boq-cell-rate">${__("Rate")}</span>
				<span class="boq-cell boq-cell-cbd">${__("CBD")}</span>
			</div>
		`);
	}

	const original_onload = settings.onload;

	settings.onload = function (treeview) {
		original_onload && original_onload(treeview);

		inject_styles();
		add_header(treeview);

		$(treeview.body)
			.off("click.boqCbd")
			.on("click.boqCbd", ".boq-cbd-link", function (event) {
				event.preventDefault();
				event.stopPropagation();
				frappe.set_route("Form", "Cost Break Down", $(this).attr("data-cbd"));
			});
	};
})();

