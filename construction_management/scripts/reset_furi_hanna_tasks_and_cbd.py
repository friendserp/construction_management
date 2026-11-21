# Furi Hanna Road - reset Tasks + Cost Break Downs and restore all CBD child rows.
#
# Workflow:
#   1. LOCAL site  -> run with mode="export" to snapshot CBDs (all child rows) and links.
#   2. Copy the JSON file to the remote server.
#   3. REMOTE site -> run with mode="import" to delete and rebuild.
#
# Tasks are recreated from the BOQ DATA embedded in this file.
# Cost Break Downs are recreated from the exported JSON so every child row
# (machinery / manpower / material) is preserved.
#
# LOCAL export:
#   bench --site klc execute \
#     construction_management.scripts.reset_furi_hanna_tasks_and_cbd.run \
#     --kwargs '{"mode":"export","snapshot_file":"/tmp/furi_hanna_snapshot.json"}'
#
# REMOTE import:
#   bench --site <site> execute \
#     construction_management.scripts.reset_furi_hanna_tasks_and_cbd.run \
#     --kwargs '{"mode":"import","snapshot_file":"/tmp/furi_hanna_snapshot.json","confirm":"Furi Hanna Road","dry_run":False}'
#
# Import always writes a backup next to the snapshot before changing anything.

import json

import frappe
from frappe.utils import flt, now

PROJECT = "Furi Hanna Road"
DEFAULT_SNAPSHOT = "/tmp/furi_hanna_snapshot.json"

META_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"parent",
	"parentfield",
	"parenttype",
	"__islocal",
	"__unsaved",
	"_user_tags",
	"_comments",
	"_assign",
	"_liked_by",
}


def log(msg):
	print(msg)


def L(title, desc, unit, qty, rate, amount):
    return {"title": title, "desc": desc, "unit": unit, "qty": qty, "rate": rate, "amount": amount}


def G(title, children):
    return {"title": title, "children": children}


DATA = [
    G("BILL No. 1: GENERAL", [
        G("ACCOMODATION, SERVICES, AND ATTENDANCE FOR THE ENGINEER'S STAFF", [
            L("104 P3.1", "Provision of Office with all Furniture's and facilities, and the necessary services and maintenance as per the contract", "Month", 19.00, 240000.00, 4560000.00),
            L("104 P3.2 (i)", "Provision of Laboratory with full Lab Equipment's and all necessary services and Maintenances, or Services for all accessories as stated in the contract", "Month", 19.00, 350000.00, 6650000.00),
            L("104 P3.2.1 (ii)", "All additional laboratory Test Required", "PS", 1.00, 500000.00, 500000.00),
            L("104P3.4.1.2 (iii)", "Percentage allowed for overhead and profit for provisional sum under item 104 P3.4.1.2 (ii)", "%", None, 25.00, 125000.00),
            L("104 P3.3", "Provision of Surveying instruments including total station, automatic level with all accessories as stated in the Contract (Table 104.3/2)", "Month", 19.00, 108000.00, 2052000.00),
            L("104 P3.4", "Provision of Computers, Printers, Scanner, WiFi Internet connection for office, soft wares, cost of stationeries and others in lump sum as stated in the 104.1/2 (Sec.6 - f ii part two) (Table 104.1/2)", "LS", 1.00, 560000.00, 560000.00),
            L("104 P5 (a)", "Provision of Double Cabin, Pickup/electric for engineer and his staff", "No.", 1.00, 10500000.00, 10500000.00),
            L("104 P5 (b)", "Provision of Mini bus/electric for engineer and his staff", "No.", 3.00, 10500000.00, 31500000.00),
            L("104 P6", "Provision of Servicing, maintenance and repair of vehicles for the engineer amd his staff", "Veh-Month", 76.00, 90000.00, 6840000.00),
            L("104 P7.1", "Drivers for Engineers vehicles", "Man-Month", 76.00, 16000.00, 1216000.00),
            L("104P7.2", "Three Chairman for the Engineer's Surveyors", "Man-Month", 152.00, 12500.00, 1900000.00),
            L("SP 104 P7.3", "Three Labor for Laboratory", "Man-Month", 152.00, 12500.00, 1900000.00),
            L("SP 104 P7.4", "Assistant Secretary", "Man-Month", 19.00, 12500.00, 237500.00),
            G("104 P14", [
                L("SP(104P14 4(a)", "Provision of pre-Paid Mobile Card for 5 mobile apparatus, maximum amount of Birr 1000 per month for each apparatus", "Month", 95.00, 1250.00, 118750.00),
            ]),
        ]),
    ]),
    G("BILL No. 2: Earthworks", [
        G("201 Clearing and Grubbing", [
            L("201 P1", "Clearing and Grubbing", "Ha", 8.82, 184001.00, 1622888.82),
        ]),
        G("204 Embankment Construction", [
            L("204P1", "Borrow to fill with granular material min CBR 15, PI-12 & max grain size 150mm", "m3", 63310.60, 1131.00, 71604288.60),
            L("204P3.1", "Soft Excavation to wasste", "m3", 193132.64, 300.96, 58125199.33),
            L("205 P1/P2", "Roadbed Prepartion", "m2", 75000.00, 58.00, 4350000.00),
            L("SP205P7", "Capping layer with Granular material min CBR 15 & PI-12, Max, grain size 150mm irrespective of material type and hauling distance", "m3", 18340.16, 1131.00, 20742720.96),
        ]),
    ]),
    G("Bill No.3: Sub Bases and Bases", [
        G("Section 300: Sub base and Road Bases", [
            L("301P1.1 (i)", "Natural aggregate, crushed gravel/stone or blended with shall satisfy special specifications compacted to 97% of AASHTO T180. 130mm layers thickness sub bases for carriage ways & 200mm layer thickness for walkwaysas per pavment thickness table", "m3", 11769.11, 1959.00, 23055686.49),
            L("302P2.1 (i)", "Crushed stone base compacted to 100% of AASHTO Test S-11 density, 120mm layers thickness as per pavement thickness table.", "m3", 5551.68, 3025.00, 16793832.00),
        ]),
    ]),
    G("Bill No.4: Bituminous Pavements", [
        G("Bituminous Pavements", [
            L("401 P.1.1", "Supply and spray MC-30 Cut Back Asphalt Prime Coat at an application rate of 1.0Lt/m2", "Lit", 46542.25, 276.00, 12845661.00),
            L("403 P4", "Dense graded asphalt AC in wearing courses, 50mm nominated compacted layer thickness, 14mm nominal aggregate size with 80/100 pen. bitumen", "m2", 46542.25, 2472.00, 115052442.00),
        ]),
    ]),
    G("Bill No.6: Structures", [
        G("6.1: Drains, Culverts and Retaining Walls", [
            G("Retaining Wall Excvation in Soft Material", [
                L("601 P1.1", "Excavation of soft material irrespective of depth", "m3", 2987.32, 297.00, 887234.04),
            ]),
            G("Retaining Wall and Backfilling", [
                L("601 P2.2", "Using Imported selected Material", "m3", 896.19, 1454.00, 1303060.26),
            ]),
            G("Concrete Structures", [
                L("603P1.2(b)", "In invert Slab to Portals or Rectangular (Box/Slab/Head walls) culverts, retaining walls and Gutter paved water way including formwork, joints and U2 surface finish (Grade C-20)", "m3", 544.89, 14622.00, 7967381.58),
                L("603P1.3(b)", "In invert Slab to Portals or Rectangular (Box/Slab/Head walls) culverts, Gutter including fleswork, formwork, joints and U2 surface finish (Grade -25)", "m3", 421.60, 16748.00, 7060956.80),
            ]),
            G("Concrete Parapets and Steel Railings", [
                L("606 P16", "RHS railing including RC concrete", "Lm", 765.00, 11931.48, 9127582.20),
            ]),
            G("Drainage Pipes and weepholes", [
                L("606 P19.2.i", "100mm dia UPVC drainage pipes (prov)", "Lm", 36.69, 850.00, 31186.50),
                L("606 P19.2.ii", "110mm dia UPVC drainage pipes (weep hole)", "Lm", 134.10, 1200.00, 160920.00),
                L("606 P19.2.iii", "50mm dia UPVC drainage pipes (prov)", "Lm", 36.69, 650.00, 23848.50),
            ]),
            G("Culverts (Slab/Box/Pipe) excavation in soft material", [
                L("610 P1.1", "Excavation of soft material irrespective of depth", "m3", 805.41, 297.00, 239206.77),
            ]),
            G("Excavation in soft material (Gutter)", [
                L("610 P1 (1)(i)", "0m up to 1.5m", "m3", 3280.68, 297.00, 974361.96),
                L("610 P1 (1)(ii)", "From 1.5m and up to 3.0m", "m3", 820.17, 612.00, 501944.04),
            ]),
            G("Culverts backfilling (Slab/Box/Pipe)", [
                L("610 P2.2", "Using imported selected material", "m3", 196.15, 1454.00, 285202.10),
            ]),
            G("Side Drain backfilling (Gutter)", [
                L("610 P2.2", "Using imported selected material", "m3", 403.87, 1454.00, 587226.98),
            ]),
            G("Electrical conduit Pipe backfilling", [
                L("610 P2.2", "Using Imported Selected Material (a minimum 5cm sand shall be used around the conduit)", "m3", 6098.08, 1500.00, 9147120.00),
            ]),
            G("Culverts (crossing) RC pipe culverts on class 'A' reinforced concrete bedding", [
                L("610 P3(C)1.2", "1200mm (48\") internal diameter", "m", 21.00, 61737.00, 1296477.00),
            ]),
            G("Steel Reinforcement (Slab/Box/Pipe/head walls) Culverts", [
                L("610 P10.1", "High Tensile Steel Reinforcements in Culverts", "ton", 41.94, 210000.00, 8807400.00),
            ]),
            G("Storm Water Pipes", [
                L("611 P6.1", "1200mm (48\") internal diameter RC Pipe Culvert on Class 'B' Bedding", "m", 6356.00, 26608.00, 169120448.00),
            ]),
            G("Sub Soil Drains", [
                L("611 P21", "110mm dia. UPVC Perforated drainage Pipes including Geotextile and aggregate", "m", 100.00, 1650.00, 165000.00),
            ]),
            G("RC Concrete Manhole", [
                L("614 P1.3", "Depth range 2.0-3.5m", "No.", 390.00, 44800.00, 17472000.00),
                L("614 P1.4", "Depth range 3.5-4.5m", "No.", 20.00, 78200.00, 15640000.00),
                L("614 P7", "Concrete Cover (Refer drawing Pack-8-S-03, Manhole detail)", "No.", 410.00, 10500.00, 4305000.00),
                L("614 P7.1", "Concrete Cover (Refer drawing Pack-8-G.6, Gutter detail)", "No.", 2589.00, 8300.00, 21488700.00),
            ]),
            G("RC Concrete Manhole (LV) for electrical conduit", [
                L("614 P1.2", "Depth range 1.5-2.0m", "No.", 89.00, 38500.00, 3426500.00),
                L("614 P7", "Concrete Manhole cover (for electrical conduit)", "No.", 89.00, 8300.00, 738700.00),
            ]),
            G("Curbs and Footpaths", [
                L("615 P1.a", "Class 25 concrete curbing including support concrete and formwork (see detail dwg) Type B (Inner asphalt curbs)", "Lm", 10248.08, 1899.00, 19461103.92),
                L("615 P1.b", "Class 25 concrete curbing including support concrete and formwork (see detail dwg) Type A (Outer walkway curbs)", "Lm", 10248.08, 1301.00, 13332752.08),
                L("615 P14.a", "Foot path (Side Walk) 300x300x50mm pre-colored concrete block on cement stabilized sand base including any jointing work. The shape and size are subjected to prior approval of Engineer.", "m2", 21758.19, 1523.00, 33137723.37),
            ]),
        ]),
    ]),
    G("Bill No.7: Incidental Works", [
        G("701: Incidental Works", [
            L("701 P1.2", "200mm nominal thickness stone pitching (paved water way)", "m2", 43.35, 1870.00, 81064.50),
            L("701 P2.2", "Cement Mortared Stone/Masonry Walls (Class B) for Retaining walls", "m3", 6353.43, 7390.00, 46951847.70),
            L("701 P2", "Sheathing Material (for retaining/end walls/weep holes)", "m3", 901.25, 2858.00, 2575772.50),
            L("701 P3", "Grade 15 concrete (lean concrete)", "m3", 155.67, 12454.00, 1938714.18),
        ]),
        G("Road Signs", [
            L("709 P1.3", "Sign faces with painted background, legends, symbols, lettering and boarders in Engineering grade retro-reflective material with signboard from 2mm thick aluminum", "m2", 25.84, 16381.00, 423285.04),
            L("709 P2.1", "Tubular Steel Post Mounting (includes cost of excavating for erecting, the necessary concreting, the post and all other expenses)", "No.", 68.00, 7664.00, 521152.00),
        ]),
        G("Pavement Marking", [
            L("710 P2", "Set-out of Pavement marking", "Ls", 1.00, 450000.00, 450000.00),
            L("710 P3.3", "Separation Lines: White thermoplastic road marking 150mm wide broken lines (as per drawing)", "m", 2292.74, 383.00, 878119.42),
            L("710 P3.5", "Barrier Lines: White thermoplastic road marking 150mm wide continuous line", "m", 7675.84, 419.00, 3216176.96),
            L("710 P3.23", "Cross Walk line - Zebra Crossing 500mm wide Continuous line", "m", 227.23, 1466.50, 333232.80),
            L("710 P3.24", "Stop lines - 500mm wide continuous line", "m", 228.16, 1466.50, 334596.64),
        ]),
    ]),
    G("Bill No. 8: Electrical Works", [
        G("Electrical Works", [
            L("802.5 (i)", "Street Lighting Work", "PS", None, None, 69355234.38),
            L("802.5 (ii)", "An Additional percentage allowance for overhead and profit applied to PS 802.5 (i)", "%", None, 20.00, 13871046.88),
        ]),
    ]),
    G("Schedule of Dayworks", [
        G("Schedule 1: labour", [
            L("L.001", "Laborer", "hr", 500.00, 144.53, 72265.00),
            L("L.002", "Gang Chief", "hr", 50.00, 245.70, 12285.00),
            L("L.003", "Brick layer", "hr", 50.00, 346.80, 17340.00),
            L("L.004", "Carpenter", "hr", 50.00, 361.35, 18067.50),
            L("L.005", "Shutter hand", "hr", 50.00, 534.75, 26737.50),
            L("L.006", "Steel Fixer", "hr", 25.00, 346.80, 8670.00),
            L("L.007", "Mason", "hr", 50.00, 375.80, 18790.00),
            L("DW-OH.1", "Allow percent of sub-total for Contractor's Overheads and profit on Day Work Labour", "%", None, 20.00, 34831.00),
        ]),
        G("Schedule 2: Material", [
            L("M.001", "Cement", "Kg", 3000.00, 12.80, 38400.00),
            L("M.002", "19mm Aggregate for concrete", "m3", 400.00, 1200.00, 480000.00),
            L("M.003", "Concrete sand", "m3", 300.00, 1600.00, 480000.00),
            L("M.004", "Dressed Masonry", "m3", 400.00, 980.00, 392000.00),
            L("M.005", "Hollow concrete block (400x200xx200mm)", "no", 200.00, 58.00, 11600.00),
            L("M.006", "Plaster", "m2", 100.00, 320.00, 32000.00),
            L("M.007", "High Tensile Steel (All diameters)", "kg", 3000.00, 148.00, 444000.00),
            L("M.008", "Mild Steel (All diameters)", "kg", 1000.00, 148.00, 148000.00),
            L("M.009", "MC 30 cut back bitumen", "Lit", 500.00, 172.00, 86000.00),
            L("M.010", "Bitumen 85/100", "Lit", 800.00, 134.00, 107200.00),
            L("M.011", "9.5mm Aggergate for surfacing", "m3", 200.00, 1826.80, 365360.00),
            L("M.012", "19mm Aggergate for surfacing", "m3", 200.00, 1826.80, 365360.00),
            L("M.013", "100Kg Riprap", "m3", 200.00, 1082.50, 216500.00),
            L("DW-OH.2", "Allow percent of sub-total for Contractor's Overheads and profit on Day Work Material", "%", None, 20.00, 633284.00),
        ]),
        G("Schedule 3: Construction Equipment including fuel", [
            L("P.001", "Concrete vibrator", "Hr.", 300.00, 86.00, 25800.00),
            L("P.002", "Concrete mixer 14/10", "Hr.", 300.00, 145.00, 43500.00),
            L("P.003", "Bitumen distributer", "Hr.", 300.00, 2600.00, 780000.00),
            L("P.004", "Motorized grader-Cat 140H or similar", "Hr.", 500.00, 1600.00, 800000.00),
            L("P.005", "Dozer - Cat D6 or equivalent", "Hr.", 200.00, 400.00, 80000.00),
            L("P.006", "Dozer - Cat D7 or equivalent", "Hr.", 200.00, 800.00, 160000.00),
            L("P.007", "Dozer - Cat D8 or equivalent", "Hr.", 200.00, 4500.00, 900000.00),
            L("P.008", "Excavator - Cat 320 or similar", "Hr.", 200.00, 3200.00, 640000.00),
            L("P.009", "Excavator - Cat 300 or similar", "Hr.", 200.00, 2900.00, 580000.00),
            L("P.010", "Tracked back actor", "Hr.", 200.00, 1800.00, 360000.00),
            L("P.011", "Front end loader < 105cu.m capacity", "Hr.", 200.00, 1800.00, 360000.00),
            L("P.012", "Front end loader > 105cu.m capacity", "Hr.", 200.00, 1800.00, 360000.00),
            L("P.013", "18 to 30 tonner tipper truck", "Hr.", 200.00, 2000.00, 400000.00),
            L("P.014", "Articulated dump truck", "Hr.", 200.00, 2200.00, 440000.00),
            L("P.015", "7 to 12 tons lorries", "Hr.", 200.00, 1600.00, 320000.00),
            L("P.016", "Water bowser minimum Capacity < 10000 liters", "Hr.", 200.00, 1800.00, 360000.00),
            L("P.017", "Water bowser minimum Capacity > 10000 liters", "Hr.", 200.00, 1800.00, 360000.00),
            L("P.018", "Steel flat wheet roller minimum mass 5 tons", "Hr.", 200.00, 1600.00, 320000.00),
            L("P.019", "Grid roller mass > 10 tons", "Hr.", 200.00, 1600.00, 320000.00),
            L("P.020", "Pneumatic tyred roller mass > 10ton", "Hr.", 200.00, 1800.00, 360000.00),
            L("P.021", "Small Vibrating roller - Bomag 90 or similar", "Hr.", 200.00, 1300.00, 260000.00),
            L("P.022", "Agricultural tractor", "Hr.", 200.00, 1350.00, 270000.00),
            L("P.023", "4 wheel drive pick up", "Hr.", 500.00, 450.00, 225000.00),
            L("P.024", "Compressor", "Hr.", 300.00, 450.00, 135000.00),
            L("P.025", "Jack hammer", "Hr.", 300.00, 1350.00, 405000.00),
            L("P.026", "water pump", "Hr.", 300.00, 620.00, 186000.00),
            L("DW-OH.3", "Allow percent of sub-total for Contractor's Overheads and profit on Day Work Equipment", "%", None, 20.00, 1890060.00),
        ]),
    ]),
]


def load_boq_data():
	return DATA


def count_boq_tasks(nodes):
	total = 0
	for node in nodes:
		total += 1
		if "children" in node:
			total += count_boq_tasks(node["children"])
	return total


# ---------------------------------------------------------------- signatures


def old_task_sig(task, by_name, cache):
	name = task.get("name")
	if name in cache:
		return cache[name]
	parent_sig = ()
	parent = by_name.get(task.get("parent_task"))
	if parent:
		parent_sig = old_task_sig(parent, by_name, cache)
	if task.get("is_group"):
		node = ("G", (task.get("subject") or "").strip())
	else:
		node = (
			"L",
			(task.get("custom_pay_item_no") or "").strip(),
			(task.get("subject") or "").strip(),
		)
	sig = parent_sig + (node,)
	cache[name] = sig
	return sig


def new_task_sig(node, parent_sig, is_group, subject):
	if is_group:
		item = ("G", subject)
	else:
		item = ("L", node["title"], subject)
	return parent_sig + (item,)


def sig_to_list(sig):
	return [list(x) for x in sig]


def list_to_sig(value):
	return tuple(tuple(x) if isinstance(x, list) else x for x in value)


# ---------------------------------------------------------------- export


def build_link_candidates(tasks, cbds):
	"""Existing links first, then exact task.subject / pay-item matches."""
	by_name = {t["name"]: t for t in tasks}
	cache = {}
	sig_by_task = {t["name"]: old_task_sig(t, by_name, cache) for t in tasks}
	sig_by_subject = {}
	sig_by_payitem = {}
	for t in tasks:
		sig = sig_by_task[t["name"]]
		if t.get("subject"):
			sig_by_subject.setdefault(t["subject"], []).append(sig)
		if t.get("custom_pay_item_no"):
			sig_by_payitem.setdefault(t["custom_pay_item_no"], []).append(sig)

	links = []
	used_tasks = set()
	for t in tasks:
		if t.get("cost_break_down"):
			links.append(
				{
					"task_sig": sig_to_list(sig_by_task[t["name"]]),
					"task_name": t["name"],
					"cbd": t["cost_break_down"],
					"source": "task.cost_break_down",
				}
			)
			used_tasks.add(t["name"])

	for c in cbds:
		if not c.get("task"):
			continue
		if c["task"] in used_tasks:
			continue
		links.append(
			{
				"task_sig": sig_to_list(sig_by_task[c["task"]]),
				"task_name": c["task"],
				"cbd": c["name"],
				"source": "cbd.task",
			}
		)
		used_tasks.add(c["task"])

	# Only auto-link exact matches; ambiguous matches are left for manual review.
	for c in cbds:
		if any(link["cbd"] == c["name"] for link in links):
			continue
		matches = sig_by_subject.get(c.get("work_item")) or sig_by_payitem.get(c.get("work_item"))
		if matches and len(matches) == 1:
			sig = matches[0]
			task_name = next(t["name"] for t in tasks if sig_by_task[t["name"]] == sig)
			if task_name not in used_tasks:
				links.append(
					{
						"task_sig": sig_to_list(sig),
						"task_name": task_name,
						"cbd": c["name"],
						"source": "exact work_item match",
					}
				)
				used_tasks.add(task_name)

	return links


def normalize_cbd_rows(cbd):
	"""Repair machinery/manpower counts that the CBD form has saved as 0."""
	for row in cbd.get("machineries") or []:
		count = flt(row.get("no"))
		uf = flt(row.get("uf")) or 1
		rental = flt(row.get("hourly_rental"))
		hourly = flt(row.get("hourly_cost"))
		if count <= 0 and rental and hourly:
			row["no"] = round(hourly / (uf * rental), 6)
	for row in cbd.get("manpowers") or []:
		count = flt(row.get("no"))
		uf = flt(row.get("uf")) or 1
		indexed = flt(row.get("indexed_hourly_cost"))
		hourly = flt(row.get("hourly_cost"))
		if count <= 0 and indexed and hourly:
			row["no"] = round(hourly / (uf * indexed), 6)
	return cbd


def export_snapshot(snapshot_file=None, repair=True):
	snapshot_file = snapshot_file or DEFAULT_SNAPSHOT
	tasks = frappe.get_all(
		"Task", filters={"project": PROJECT}, fields=["*"], order_by="creation asc"
	)
	task_docs = []
	for t in tasks:
		task_docs.append(frappe.get_doc("Task", t.name).as_dict())

	cbd_names = frappe.get_all("Cost Break Down", pluck="name", order_by="creation asc")
	cbd_docs = [frappe.get_doc("Cost Break Down", name).as_dict() for name in cbd_names]
	if repair:
		for cbd in cbd_docs:
			normalize_cbd_rows(cbd)

	links = build_link_candidates(task_docs, cbd_docs)
	linked_cbds = {link["cbd"] for link in links}

	# Links that live on tasks outside this project. Those tasks are not deleted,
	# so they can be re-linked by name after the CBDs are recreated.
	external_links = []
	for t in frappe.get_all(
		"Task",
		filters={"cost_break_down": ["is", "set"]},
		fields=["name", "project", "cost_break_down"],
	):
		if t["project"] != PROJECT:
			external_links.append(
				{
					"task_name": t["name"],
					"cbd": t["cost_break_down"],
					"source": "external task.cost_break_down",
				}
			)

	data = {
		"project": PROJECT,
		"exported_at": now(),
		"tasks": task_docs,
		"cbds": cbd_docs,
		"links": links,
		"external_links": external_links,
		"unlinked_cbds": [
			{"name": c["name"], "work_item": c.get("work_item")}
			for c in cbd_docs
			if c["name"] not in linked_cbds
		],
	}
	with open(snapshot_file, "w") as f:
		f.write(frappe.as_json(data))
	log("Exported {} tasks, {} CBDs, {} links, {} external links -> {}".format(
		len(task_docs), len(cbd_docs), len(links), len(external_links), snapshot_file
	))
	log("Edit the 'links' list in that JSON before import to add missing task/CBD pairs.")
	return snapshot_file


# ---------------------------------------------------------------- cleanup


def child_table_doctypes(doctype):
	return [df.options for df in frappe.get_meta(doctype).get_table_fields()]


def clear_link_fields(target_doctype, names):
	if not names:
		return
	fields = frappe.get_all(
		"DocField",
		filters={"fieldtype": "Link", "options": target_doctype},
		fields=["parent", "fieldname"],
	)
	fields += frappe.get_all(
		"Custom Field",
		filters={"fieldtype": "Link", "options": target_doctype},
		fields=["dt as parent", "fieldname"],
	)
	for f in fields:
		parent, field = f["parent"], f["fieldname"]
		if not frappe.db.has_column(parent, field):
			continue
		try:
			frappe.db.sql(
				"update `tab{}` set `{}`=null where `{}` in %s".format(parent, field, field),
				(names,),
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "reset_furi_hanna clear_link_fields")


def purge_cost_break_downs():
	names = frappe.get_all("Cost Break Down", pluck="name")
	if not names:
		return []
	for child in child_table_doctypes("Cost Break Down"):
		frappe.db.delete(child, {"parent": ["in", names], "parenttype": "Cost Break Down"})
	clear_link_fields("Cost Break Down", names)
	frappe.db.delete("Cost Break Down", {"name": ["in", names]})
	return names


def purge_project_tasks():
	names = frappe.get_all("Task", filters={"project": PROJECT}, pluck="name")
	if not names:
		return []
	for child in child_table_doctypes("Task"):
		frappe.db.delete(child, {"parent": ["in", names], "parenttype": "Task"})
	frappe.db.delete("Task", {"name": ["in", names]})
	return names


# ---------------------------------------------------------------- task creation


def collect_units(nodes, acc):
	for n in nodes:
		if "children" in n:
			collect_units(n["children"], acc)
		elif n.get("unit"):
			acc.append(n["unit"])


def ensure_uoms(data):
	units = []
	collect_units(data, units)
	canonical = {}
	for u in units:
		canonical.setdefault(u.lower(), u)
	for u in sorted(set(canonical.values())):
		if not frappe.db.exists("UOM", u):
			frappe.get_doc(
				{"doctype": "UOM", "uom_name": u, "enabled": 1}
			).insert(ignore_permissions=True)
	return canonical


def clean(text, limit=140):
	text = (text or "").strip()
	return text[:limit]


def create_tasks_from_boq():
	data = load_boq_data()
	uom_map = ensure_uoms(data)
	by_sig = {}

	def walk(node, parent, parent_sig):
		is_group = "children" in node
		if is_group:
			subject = clean(node["title"])
		else:
			subject = clean(node["desc"], 130)

		task = frappe.new_doc("Task")
		task.subject = subject
		task.project = PROJECT
		task.status = "Open"
		task.is_group = 1 if is_group else 0
		task.ignore_permissions = 1
		if parent:
			task.parent_task = parent

		if not is_group:
			task.custom_pay_item_no = node["title"]
			if node.get("unit"):
				task.custom_unit = uom_map.get(node["unit"].lower(), node["unit"])
			if node.get("qty") is not None:
				task.custom_contract_qty = node["qty"]
			if node.get("rate") is not None:
				task.custom_unit_rate = node["rate"]
			if node.get("amount") is not None:
				task.custom_contract_amount = node["amount"]

		task.insert(ignore_permissions=True)
		sig = new_task_sig(node, parent_sig, is_group, subject)
		by_sig[sig] = task.name

		if is_group:
			for child in node["children"]:
				walk(child, task.name, sig)

	for bill in data:
		walk(bill, None, ())
	return by_sig


# ---------------------------------------------------------------- CBD creation


def clean_doc(d):
	out = {}
	for key, value in d.items():
		if key in META_FIELDS:
			continue
		if isinstance(value, list):
			out[key] = [clean_doc(row) for row in value]
		else:
			out[key] = value
	return out


def recreate_cbds(cbd_docs):
	mapping = {}
	for old in cbd_docs:
		data = clean_doc(old)
		data["doctype"] = "Cost Break Down"
		data["task"] = None
		normalize_cbd_rows(data)
		doc = frappe.get_doc(data)
		doc.insert(ignore_permissions=True)
		mapping[old["name"]] = doc.name
	return mapping


# ---------------------------------------------------------------- import


def import_snapshot(snapshot_file=None, dry_run=True, confirm=None):
	snapshot_file = snapshot_file or DEFAULT_SNAPSHOT
	if not dry_run and confirm != PROJECT:
		frappe.throw(
			"Refusing to change data. Pass confirm='{}' and dry_run=False.".format(PROJECT)
		)

	with open(snapshot_file) as f:
		snapshot = json.loads(f.read())

	if snapshot.get("project") != PROJECT:
		frappe.throw(
			"Snapshot is for project {!r}, expected {!r}".format(
				snapshot.get("project"), PROJECT
			)
		)

	cbd_docs = snapshot.get("cbds") or []
	links = snapshot.get("links") or []
	external_links = snapshot.get("external_links") or []

	if dry_run:
		existing_tasks = frappe.get_all(
			"Task", filters={"project": PROJECT}, pluck="name"
		)
		existing_cbds = frappe.get_all("Cost Break Down", pluck="name")
		log("DRY RUN")
		log("Would delete {} Furi Hanna tasks and {} CBDs".format(
			len(existing_tasks), len(existing_cbds)
		))
		log("Would recreate {} tasks from BOQ DATA and {} CBDs from snapshot".format(
			count_boq_tasks(load_boq_data()), len(cbd_docs)
		))
		log("Would apply {} links (+{} external)".format(
			len(links), len(external_links)
		))
		return

	backup = snapshot_file + ".before_import.json"
	export_snapshot(backup, repair=False)
	log("Backup written to {}".format(backup))

	deleted_cbds = purge_cost_break_downs()
	deleted_tasks = purge_project_tasks()
	frappe.db.commit()
	log("Deleted {} CBDs and {} Furi Hanna tasks".format(
		len(deleted_cbds), len(deleted_tasks)
	))

	tasks_by_sig = create_tasks_from_boq()
	frappe.db.commit()
	log("Created {} tasks from BOQ DATA".format(len(tasks_by_sig)))

	cbd_map = recreate_cbds(cbd_docs)
	frappe.db.commit()
	log("Created {} CBDs from snapshot".format(len(cbd_map)))

	linked = 0
	missing_tasks = 0
	missing_cbds = 0
	for link in links:
		sig = list_to_sig(link.get("task_sig") or [])
		task = tasks_by_sig.get(sig)
		new_cbd = cbd_map.get(link.get("cbd"))
		if not task:
			missing_tasks += 1
			continue
		if not new_cbd:
			missing_cbds += 1
			continue
		frappe.db.set_value("Task", task, "cost_break_down", new_cbd)
		frappe.db.set_value("Cost Break Down", new_cbd, "task", task)
		linked += 1
	frappe.db.commit()

	external_linked = 0
	for link in external_links:
		new_cbd = cbd_map.get(link.get("cbd"))
		if not new_cbd or not frappe.db.exists("Task", link.get("task_name")):
			continue
		frappe.db.set_value("Task", link["task_name"], "cost_break_down", new_cbd)
		external_linked += 1
	frappe.db.commit()

	log("Linked {} tasks to CBDs ({} task signatures not found, {} CBDs not found)".format(
		linked, missing_tasks, missing_cbds
	))
	log("Linked {} external tasks".format(external_linked))
	log("Unlinked CBDs in snapshot: {}".format(len(snapshot.get("unlinked_cbds") or [])))
	log("DONE")


def run(mode="export", snapshot_file=None, dry_run=True, confirm=None):
	if mode == "export":
		return export_snapshot(snapshot_file)
	if mode == "import":
		return import_snapshot(snapshot_file, dry_run=dry_run, confirm=confirm)
	frappe.throw("mode must be 'export' or 'import'")

