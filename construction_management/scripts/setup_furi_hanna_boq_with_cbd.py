# Furi Hanna Road - BOQ Tasks Importer with CBD Linking
# Creates the BOQ as a Task tree on project "Furi Hanna Road" and links Cost Break Down documents.
#
# Run: bench --site klc execute construction_management.scripts.setup_furi_hanna_boq_with_cbd
#
# Idempotent: re-running updates existing tasks and CBD links.

import frappe
from frappe.utils import flt

PROJECT = "Furi Hanna Road"


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


def collect_units(nodes, acc):
    for n in nodes:
        if "children" in n:
            collect_units(n["children"], acc)
        elif n.get("unit"):
            acc.append(n["unit"])


def sum_amounts(nodes):
    total = 0.0
    for n in nodes:
        if "children" in n:
            total += sum_amounts(n["children"])
        elif n.get("amount") is not None:
            total += n["amount"]
    return total


def ensure_uoms():
    units = []
    collect_units(DATA, units)
    canonical = {}
    for u in units:
        canonical.setdefault(u.lower(), u)
    for u in sorted(set(canonical.values())):
        if not frappe.db.exists("UOM", u):
            frappe.get_doc({"doctype": "UOM", "uom_name": u, "enabled": 1}).insert(ignore_permissions=True)
            print("  created UOM:", u)
    return canonical


def clean(text, limit=140):
    text = (text or "").strip()
    return text[:limit]


def get_or_create_cbd(work_item, unit, rate, amount, qty=None):
    """Get or create a Cost Break Down document for a task."""
    # Try to find existing CBD with matching work_item
    cbd_name = frappe.db.exists("Cost Break Down", {"work_item": work_item})
    if cbd_name:
        cbd = frappe.get_doc("Cost Break Down", cbd_name)
        # Update fields if they've changed
        if cbd.unit != unit:
            cbd.unit = unit
        # Map rate and amount to direct_cost and total_unit_cost
        if flt(cbd.direct_cost) != flt(rate):
            cbd.direct_cost = flt(rate)
        if flt(cbd.total_unit_cost) != flt(amount):
            cbd.total_unit_cost = flt(amount)
        cbd.save(ignore_permissions=True)
        return cbd.name
    
    # Create new CBD
    cbd = frappe.new_doc("Cost Break Down")
    cbd.naming_series = "CBD-"
    cbd.work_item = work_item
    cbd.unit = unit
    cbd.direct_cost = flt(rate)
    cbd.total_unit_cost = flt(amount)
    cbd.insert(ignore_permissions=True)
    return cbd.name


stats = {"created": 0, "updated": 0, "groups": 0, "leaves": 0, "amount": 0.0}
EXISTING = {}


def create_node(node, parent, uom_map):
    is_group = "children" in node
    title = node["title"]

    existing = EXISTING.get((parent or "", title))

    if existing:
        task = frappe.get_doc("Task", existing)
        if not task.custom_pay_item_no:
            task.custom_pay_item_no = title
        if not task.custom_contract_qty and node.get("qty") is not None:
            task.custom_contract_qty = node["qty"]
        if not task.custom_unit_rate and node.get("rate") is not None:
            task.custom_unit_rate = node["rate"]
        if not task.custom_contract_amount and node.get("amount") is not None:
            task.custom_contract_amount = node["amount"]
        if not task.custom_unit and node.get("unit"):
            task.custom_unit = uom_map.get(node["unit"].lower(), node["unit"])
        
        # Link CBD to task
        if node.get("qty") is not None and node.get("rate") is not None and node.get("amount") is not None:
            work_item = f"{title[:50]}"
            cbd_name = get_or_create_cbd(work_item, node["unit"], node["rate"], node["amount"], node["qty"])
            task.cost_break_down = cbd_name
        
        task.save(ignore_permissions=True)
        stats["updated"] += 1
    else:
        task = frappe.new_doc("Task")
        task.subject = clean(title)
        task.project = PROJECT
        task.status = "Open"
        task.ignore_permissions = 1
        if parent:
            task.parent_task = parent
        stats["created"] += 1

    task.is_group = 1 if is_group else 0

    if is_group:
        stats["groups"] += 1
        task.description = ""
        task.save(ignore_permissions=True)
        EXISTING[(parent or "", title)] = task.name
        for child in node["children"]:
            create_node(child, task.name, uom_map)
    else:
        task.custom_pay_item_no = title
        task.subject = node["desc"][:130]
        if node.get("unit"):
            task.custom_unit = uom_map.get(node["unit"].lower(), node["unit"])
        if node.get("qty") is not None:
            task.custom_contract_qty = node["qty"]
        if node.get("rate") is not None:
            task.custom_unit_rate = node["rate"]
        if node.get("amount") is not None:
            task.custom_contract_amount = node["amount"]
        
        # Link CBD to task
        if node.get("qty") is not None and node.get("rate") is not None and node.get("amount") is not None:
            work_item = f"{title[:50]}"
            cbd_name = get_or_create_cbd(work_item, node["unit"], node["rate"], node["amount"], node["qty"])
            task.cost_break_down = cbd_name
        
        task.save(ignore_permissions=True)
        EXISTING[(parent or "", title)] = task.name

    return task.name


def run():
    global EXISTING
    
    if not frappe.db.exists("Project", PROJECT):
        frappe.throw(f"Project '{PROJECT}' not found.")
    
    # Delete all existing tasks under the project directly from DB
    # This avoids on_trash errors from child tasks
    frappe.db.sql("DELETE FROM `tabTask` WHERE project = %s", (PROJECT,))
    frappe.db.commit()
    print(f"Deleted all tasks from project: {PROJECT}")
    
    # Clear EXISTING dictionary - all tasks will be created new
    EXISTING = {}
    
    print(f"Importing BOQ tasks into project: {PROJECT}")

    uom_map = ensure_uoms()
    for bill in DATA:
        create_node(bill, None, uom_map)
    frappe.db.commit()
    print("-" * 50)
    print(f"created={stats['created']}  updated={stats['updated']}")
    print(f"group tasks={stats['groups']}  leaf tasks={stats['leaves'] if 'stats' in dir() else 0}")
    print(f"total contract amount = {sum_amounts(DATA):,.2f}")
    print("DONE")


run()
