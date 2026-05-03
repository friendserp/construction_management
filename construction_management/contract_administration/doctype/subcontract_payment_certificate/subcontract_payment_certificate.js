frappe.ui.form.on("Subcontract Payment Certificate", {
	refresh(frm) {
		if (frm.is_new() && frm.doc.contract_details.length === 0) {
			["Main Contract", "Supplementary contract", "Variation orders"].forEach(type => {
				let row = frm.add_child("contract_details");
				row.type = type;
			});
			frm.refresh_field("contract_details");
		}

		if (frm.is_new() && frm.doc.deductions.length === 0) {
			["Previous Payment", "Rebate", "Retention after Rebate", "Penality", "Advance Repayment"].forEach(deduction => {
				let row = frm.add_child("deductions");
				row.deduction = deduction;
			});
			frm.refresh_field("deductions");
		}

		if (!frm.is_new()) {
			generate_flow_chart(frm);
		}
	},

	contract_agreement(frm) {
		if (!frm.doc.contract_agreement) return;

		frappe.call({
			method: "construction_management.contract_administration.doctype.subcontract_payment_certificate.subcontract_payment_certificate.get_certificate_data",
			args: {
				contract_agreement: frm.doc.contract_agreement
			},
			callback: function (r) {
				if (r.message) {
					const { contract, previous_certificates } = r.message;
					
					// Update contract details
					frm.doc.contract_details.forEach((row) => {
						if (row.type === "Main Contract") {
							frappe.model.set_value(row.doctype, row.name, "amount", contract.total_price_before_vat);
						}
					});

					// Update advances (previous payments)
					frm.clear_table("advances");
					let total_previous = 0;
					previous_certificates.forEach(cert => {
						let row = frm.add_child("advances");
						row.payment_no = cert.name;
						row.date = cert.date;
						row.total_amount = cert.net_payment;
						total_previous += cert.net_payment;
					});
					
					frm.refresh_field("advances");

					// Update deductions
					let prev_deduction = frm.doc.deductions.find(d => d.deduction === "Previous Payment");
					if (prev_deduction) {
						frappe.model.set_value(prev_deduction.doctype, prev_deduction.name, "amount", total_previous);
					}

					calculate_total(frm);
				}
			}
		});
	},

	amount_executed(frm) {
		calculate_deductions(frm);
		calculate_vats(frm);
	},

	takeoff(frm) {
		if (!frm.doc.takeoff) return;
		frappe.db.get_value("BOQ", frm.doc.boq, "t_total", (r) => {
			if (r && r.t_total) {
				frm.set_value("amount_executed", r.t_total);
			}
		});
	},

	net_sum(frm) {
		calculate_vats(frm);
	}
});

frappe.ui.form.on("SPC Contract Details", {
	amount(frm) {
		calculate_total(frm);
	},
});

frappe.ui.form.on("SPC Deduction", {
	percent(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.percent !== undefined) {
			let amount = (flt(row.percent) / 100) * flt(frm.doc.amount_executed);
			frappe.model.set_value(cdt, cdn, "amount", amount);
		}
		calculate_deductions(frm);
	},
	amount(frm) {
		calculate_deductions(frm);
	}
});

function calculate_total(frm) {
	let total = frm.doc.contract_details.reduce((sum, row) => sum + flt(row.amount), 0);
	frm.set_value("total", total);
	frm.set_value("vat", total * 0.15);
	frm.set_value("total_with_vat", total * 1.15);
	calculate_deductions(frm);
}

function calculate_deductions(frm) {
	let sub_total = frm.doc.deductions.reduce((sum, row) => sum + flt(row.amount), 0);
	frm.set_value("sub_total", sub_total);
	frm.set_value("net_sum", flt(frm.doc.amount_executed) - sub_total);
	calculate_vats(frm);
}

function calculate_vats(frm) {
	let net_sum = flt(frm.doc.net_sum);
	let vat_net = net_sum * 0.15;
	
	let retention_row = frm.doc.deductions.find(d => d.deduction === "Retention after Rebate");
	let vat_ret = retention_row ? flt(retention_row.amount) * 0.15 : 0;
	
	let vat_total = vat_net + vat_ret;
	let net_payment = net_sum - vat_total;

	frm.set_value({
		"vat_net": vat_net,
		"vat_ret": vat_ret,
		"vat_total": vat_total,
		"net_payment": net_payment
	});

	if (net_payment > 0) {
		frappe.call({
			method: "get_money_words",
			args: {
				amount: net_payment,
				currency: frm.doc.currency || "ETB"
			},
			callback: function (r) {
				if (r.message) {
					frm.set_value("net_payment_words", r.message);
				}
			}
		});
	}
}

function generate_flow_chart(frm) {
	frappe.call({
		method: "construction_management.contract_administration.doctype.subcontract_payment_certificate.subcontract_payment_certificate.get_payment_flow",
		args: { docname: frm.doc.name },
		callback: function(r) {
			if (r.message) {
				render_flow_chart(frm, r.message);
			}
		}
	});
}

function render_flow_chart(frm, flow_items) {
	let html = `
		<div class="flow-chart-container" style="margin: 20px 0; border: 1px solid #d1d8dd; border-radius: 8px; background: #fff;">
			<div style="padding: 10px 15px; border-bottom: 1px solid #d1d8dd; font-weight: bold; background: #f8f9fb;">Payment Process Flow</div>
			<div style="padding: 15px; display: flex; align-items: center; gap: 15px; overflow-x: auto;">
	`;

	flow_items.forEach((item, i) => {
		let is_current = item.current;
		html += `
			<div class="flow-step" style="display: flex; align-items: center; gap: 10px;">
				<div onclick="frappe.set_route('Form', '${item.doctype}', '${item.id}')" 
					 style="cursor: pointer; padding: 10px 15px; border: 1px solid ${is_current ? '#ff9800' : '#d1d8dd'}; 
							border-radius: 6px; background: ${is_current ? '#fff8e1' : '#fcfcfc'}; white-space: nowrap; transition: all 0.2s;">
					<span style="font-size: 18px; margin-right: 8px;">${item.icon}</span>
					<span style="font-weight: 600; color: ${is_current ? '#e65100' : '#36414c'};">${item.label}</span>
					<div style="font-size: 11px; color: #8d99a6; margin-top: 4px;">${item.id}</div>
				</div>
				${i < flow_items.length - 1 ? '<span style="color: #d1d8dd; font-size: 20px;">→</span>' : ''}
			</div>
		`;
	});

	html += `</div></div>`;
	
	frm.get_field("flow_html").$wrapper.html(html);
}