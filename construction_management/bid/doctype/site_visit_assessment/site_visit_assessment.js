// Copyright (c) 2026, Friends ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Visit Assessment", {

    setup: function(frm) {
        const material_groups = [
            {
                name: 'ms', // Stone for Masonry
                fields: ['ms_ar', 'ms_oc', 'ms_tr'],
                total_field: 'ms_tc'
            },
            {
                name: 'hd', // Stone for Hardcore
                fields: ['hd_ar', 'hd_oc', 'hd_tr'],
                total_field: 'hd_tc'
            },
            {
                name: 'sd', // Sand
                fields: ['sd_ar', 'sd_oc', 'sd_tr'],
                total_field: 'sd_tc'
            },
            {
                name: 'ew', // Eucalyptus Wood
                fields: ['ew_ar', 'ew_oc', 'ew_tr'],
                total_field: 'ew_tc'
            },
            {
                name: 'sm', // Selected Material
                fields: ['sm_ar', 'sm_oc', 'sm_tr'],
                total_field: 'sm_tp'  // Note: using sm_tp instead of sm_tc
            },
            {
                name: 'gr', // Gravel
                fields: ['gr_ar', 'gr_oc', 'gr_tr'],
                total_field: 'gr_tp'
            }
        ];

        frm.material_groups = material_groups;
    },


    ms_oc: function(frm) {
        calculate_for_group(frm, 'ms');
    },
    ms_tr: function(frm) {
        calculate_for_group(frm, 'ms');
    },

    hd_oc: function(frm) {
        calculate_for_group(frm, 'hd');
    },
    hd_tr: function(frm) {
        calculate_for_group(frm, 'hd');
    },

    sd_oc: function(frm) {
        calculate_for_group(frm, 'sd');
    },
    sd_tr: function(frm) {
        calculate_for_group(frm, 'sd');
    },

    ew_oc: function(frm) {
        calculate_for_group(frm, 'ew');
    },
    ew_tr: function(frm) {
        calculate_for_group(frm, 'ew');
    },

    sm_oc: function(frm) {
        calculate_for_group(frm, 'sm');
    },
    sm_tr: function(frm) {
        calculate_for_group(frm, 'sm');
    },

    gr_oc: function(frm) {
        calculate_for_group(frm, 'gr');
    },
    gr_tr: function(frm) {
        calculate_for_group(frm, 'gr');
    },
    asphalt_road: function(frm){
        calculate_road_total(frm)
    },
    gravel_road: function(frm){
        calculate_road_total(frm)
    },
    off_road: function(frm){
        calculate_road_total(frm)
    }


});

function calculate_road_total(frm){
    frm.set_value("total_length", (frm.doc.asphalt_road || 0) + (frm.doc.gravel_road || 0) + (frm.doc.off_road || 0) )
    frm.refresh_field("total_length")
}
function calculate_for_group(frm, group_name) {
    if (!frm.material_groups) return;
    
    const group = frm.material_groups.find(g => g.name === group_name);
    if (group) {
        calculate_total_price(frm, group);
    }
}

function calculate_total_price(frm, group) {
    console.log("group", group);
    console.log("frm.doc", frm.doc);
    let original_cost = flt(frm.doc[group.fields[1]]);
    console.log("original_cost", original_cost);
    let transportation_cost = flt(frm.doc[group.fields[2]]);
    console.log("transportation_cost", transportation_cost);
    let total_price = original_cost + transportation_cost;
    console.log("total_price", total_price);
    
    frm.set_value(group.total_field, total_price);
}