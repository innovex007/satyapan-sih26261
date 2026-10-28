"""Builds the fictional world: institutions, per-application ground truth and the planted-defect plan.
No rendering happens here, so the plan is cheap to inspect and fully determined by the seed."""
import random
from datetime import date, timedelta

SESSION_START = date(2026, 7, 1)

PREFIX = ["Shri Venkatadri", "Maa Kaveri", "Gyan Sagar", "Nava Jyoti", "Sri Lakshmi Narasimha", "Vidya Bharati Demo", "Prerana",
          "Kalpavriksha", "Jnana Deepa", "Tungabhadra Valley", "Samarth", "Himagiri", "Rajarshi Demo", "Surya Kiran", "Ananta",
          "Mahalakshmi", "Sahyadri Demo", "Bhoomi Putra", "Nilgiri Demo", "Chandrakant", "Pragati Demo", "Ekalavya Demo",
          "Dharani", "Ujjwal", "Vasundhara", "Tejas Demo", "Aruna", "Mitra Vihar", "Kshitij", "Swarnim", "Padmavati Demo", "Gokul Demo"]
SUFFIX = ["Institute of Technology", "College of Engineering", "Institute of Management Studies", "Polytechnic",
          "College of Pharmacy", "Institute of Computer Applications", "School of Architecture"]
PLACES = [  # state, region, pin prefix, fictional towns
    ("Karnataka", "Southern", "58", ["Demo Nagar", "Sample Halli", "Test Pura"]),
    ("Tamil Nadu", "Southern", "63", ["Demo Palayam", "Sample Kudi"]),
    ("Maharashtra", "Western", "41", ["Demo Wadi", "Sample Nagar", "Test Gaon"]),
    ("Gujarat", "Western", "38", ["Demo Pur", "Sample Vadi"]),
    ("Uttar Pradesh", "Northern", "22", ["Demo Ganj", "Sample Pur", "Test Nagar"]),
    ("Punjab", "Northern", "14", ["Demo Garh", "Sample Kot"]),
    ("West Bengal", "Eastern", "70", ["Demo Hat", "Sample Danga"]),
    ("Odisha", "Eastern", "75", ["Demo Pada", "Sample Vihar"]),
    ("Madhya Pradesh", "Central", "45", ["Demo Khedi", "Sample Pura"]),
    ("Assam", "North-Eastern", "78", ["Demo Gaon", "Sample Bari"]),
]
FIRST = ["Aarav", "Meera", "Rohan", "Lakshmi", "Kiran", "Suresh", "Anita", "Vikram", "Deepa", "Manoj", "Sunita", "Arjun", "Pooja",
         "Ramesh", "Kavita", "Naveen", "Shalini", "Girish", "Rekha", "Harish", "Usha", "Sanjay", "Padma", "Mohan", "Nandini"]
LAST = ["Demo-Iyer", "Sample-Rao", "Test-Patil", "Demo-Nair", "Sample-Singh", "Test-Das", "Demo-Joshi", "Sample-Reddy", "Test-Kulkarni",
        "Demo-Menon", "Sample-Gupta", "Test-Pillai", "Demo-Bose", "Sample-Shetty", "Test-Mishra"]
DESIG = ["Professor", "Associate Professor", "Assistant Professor", "Lecturer", "Lab Instructor"]

HERO_SPECS = [
    dict(id="EoA-DEMO-0417", name="Shri Venkatadri Institute of Technology", category="Extension of Approval", place=0, perm="2417"),
    dict(id="EoA-DEMO-0422", name="Maa Kaveri College of Engineering", category="Extension of Approval", place=1, perm="2422"),
    dict(id="EoA-DEMO-0431", name="Gyan Sagar Institute of Management Studies", category="New institution", place=2, perm="2431"),
    dict(id="EoA-DEMO-0440", name="Nava Jyoti Polytechnic", category="Increase in intake", place=4, perm="2440"),
]
ARCHIVE_4417 = dict(name="Sri Lakshmi Narasimha College of Engineering", perm="4417", place=0)
# archive-only institutions: filed in 2025-26, not applying this cycle (their files stay searchable for twin evidence)
ARCHIVES = [ARCHIVE_4417] + [
    dict(name=n, perm=p, place=i % 10) for i, (n, p) in enumerate([
        ("Bhoomija Institute of Technology", "3102"), ("Kshema College of Engineering", "5760"), ("Sagarika Institute of Management Studies", "6624"),
        ("Vanamali Polytechnic", "7291"), ("Tarangini College of Pharmacy", "8115"),
        ("Aksharam Institute of Technology", "2208"), ("Meghdoot College of Engineering", "3375"), ("Ranjani Institute of Computer Applications", "4926")])]
# archive institutions whose 2025 file holds a REAL sample photo: perm -> (slot, photo)
REAL_ARCHIVES = {"4417": ("lab", "twin_b_physics_lab"), "8115": ("lab", "chem_lab_1"), "2208": ("lab", "lecture_hall_1"),
                 "3375": ("lab", "library_1"), "4926": ("building", "building_front_1")}

DEFECTS = {  # type id -> (name, expected PS status, check type)
    1: ("missing_required_document", "Verification pending", "completeness"),
    2: ("expired_fire_noc", "Expired", "expiry"),
    3: ("land_area_mismatch", "Mismatch detected", "contradiction"),
    4: ("date_edited_after_signing", "Manual review required", "forensic"),
    5: ("lab_photo_reused", "Manual review required", "twin"),
    6: ("qr_content_mismatch", "Mismatch detected", "source"),
    7: ("unsigned_or_broken_signature", "Manual review required", "source"),
    8: ("duplicate_faculty_id", "Manual review required", "faculty"),
    9: ("shared_land_parcel", "Manual review required", "contradiction"),
    10: ("impossible_timeline", "Mismatch detected", "contradiction"),
}
QR_DOCS = ["fire_noc", "university_noc", "occupancy_cert"]


def nosun(d: date) -> date:
    """Generated issue/signing dates never fall on a Sunday (only the planted timeline case does)."""
    return d + timedelta(days=1) if d.weekday() == 6 else d


def fmt(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def _truth(rng: random.Random, name: str, place_idx: int, serial: int) -> dict:
    state, region, pin, towns = PLACES[place_idx]
    town = rng.choice(towns)
    area = round(rng.uniform(2.5, 14.0), 2)
    return {
        "institution_name": name,
        "state": state, "region": region, "town": town, "district": f"{town.split()[0]} District",
        "pincode": pin + f"{rng.randint(1000, 9999):04d}"[:4],
        "address": f"Survey No. {rng.randint(11, 480)}/{rng.randint(1, 9)}, {town} Road, {town}, {state}",
        "survey_no": f"{rng.randint(11, 480)}/{rng.randint(1, 9)}{rng.choice('ABC')}",
        "land_area_acres": area,
        "built_up_sqm": rng.randrange(4200, 18000, 50),
        "intake": rng.choice([60, 120, 180, 240, 300]),
        "signatory": f"Dr. {rng.choice(FIRST)} {rng.choice(LAST)}",
        "deed_date": nosun(date(2019, 1, 1) + timedelta(days=rng.randint(0, 1800))),
        "oc_no": f"DMC/OC/{rng.randint(2015, 2024)}/{rng.randint(1000, 9999)}",
        "oc_date": nosun(date(2021, 1, 1) + timedelta(days=rng.randint(0, 1200))),
        "fire_no": f"DFS/{rng.randint(100, 999)}/{rng.randint(2024, 2026)}/{rng.randint(10000, 99999)}",
        "fire_from": nosun(date(2026, 1, 5) + timedelta(days=rng.randint(0, 60))),
        "fire_till": date(2027, 1, 1) + timedelta(days=rng.randint(30, 600)),
        "univ_no": f"DSU/AFF/{rng.randint(2024, 2026)}/{rng.randint(1000, 9999)}",
        "univ_till": date(2027, 6, 30) + timedelta(days=rng.randint(0, 700)),
        "luc_no": f"DRD/LU/{rng.randint(2019, 2025)}/{rng.randint(1000, 9999)}",
        "luc_date": nosun(date(2020, 1, 1) + timedelta(days=rng.randint(0, 1500))),
        "luc_issuer": f"Demo Revenue Department, {town.split()[0]} District",
        "fee_no": f"RCPT-{rng.randint(100000, 999999)}",
        "fee_amount": rng.choice([150000, 175000, 200000, 250000]),
        "fee_date": nosun(date(2026, 4, 1) + timedelta(days=rng.randint(0, 60))),
        "aff_date": nosun(date(2026, 4, 10) + timedelta(days=rng.randint(0, 50))),
        "serial": serial,
    }


def _faculty(rng: random.Random, used_ids: set, n: int) -> list:
    out = []
    for _ in range(n):
        while True:
            fid = f"FAC-{rng.randint(100000, 999999)}"
            if fid not in used_ids:
                used_ids.add(fid)
                break
        out.append({"name": f"{rng.choice(['Dr.', 'Prof.', 'Mr.', 'Ms.'])} {rng.choice(FIRST)} {rng.choice(LAST)}",
                    "id": fid, "designation": rng.choice(DESIG)})
    return out


def build_world(seed: int, rules: dict) -> dict:
    rng = random.Random(seed)
    cats = list(rules["categories"])
    used_perm = {a["perm"] for a in ARCHIVES} | {h["perm"] for h in HERO_SPECS}
    used_fac: set = set()
    apps: list[dict] = []

    def add_app(app_id, name, category, place_idx, perm, hero):
        t = _truth(rng, name, place_idx, len(apps))
        app = {"id": app_id, "hero": hero, "category": category, "perm": perm, "truth": t,
               "faculty": _faculty(rng, used_fac, rng.randint(8, 11)),
               "required": list(rules["categories"][category]["required"]),
               "submitted": date(2026, 5, 1) + timedelta(days=rng.randint(0, 45)),
               "defects": [], "docs_used": set(), "has_last_year": False, "scan_docs": set(), "hindi_page": False}
        apps.append(app)
        return app

    for h in HERO_SPECS:
        add_app(h["id"], h["name"], h["category"], h["place"], h["perm"], True)
    names = set(h["name"] for h in HERO_SPECS) | {ARCHIVE_4417["name"]}
    weights = ["New institution"] * 5 + ["Extension of Approval"] * 11 + ["Increase in intake"] * 6 + ["Change of site"] * 4
    rng.shuffle(weights)
    for i, cat in enumerate(weights):
        while True:
            nm = f"{rng.choice(PREFIX)} {rng.choice(SUFFIX)}"
            if nm not in names:
                names.add(nm)
                break
        perm = str(rng.choice([p for p in range(1100, 9900) if str(p) not in used_perm]))
        used_perm.add(perm)
        add_app(f"EoA-2026-{101 + i:04d}", nm, cat, rng.randrange(len(PLACES)), perm, False)

    by_id = {a["id"]: a for a in apps}

    # --- last year's files: 20 institutions that are not New institutions (heroes 0417/0422/0440 included)
    cands = [a for a in apps if a["category"] != "New institution"]
    chosen = [by_id[i] for i in ("EoA-DEMO-0417", "EoA-DEMO-0422", "EoA-DEMO-0440")]
    rest = [a for a in cands if a not in chosen]
    rng.shuffle(rest)
    for a in chosen + rest[:17]:
        a["has_last_year"] = True

    # --- planted defects -------------------------------------------------------------------
    def plant(app, dtype, docs, **detail):
        app["defects"].append({"type": dtype, "docs": docs, "detail": detail})
        app["docs_used"].update(docs)

    # heroes (fixed)
    a = by_id["EoA-DEMO-0417"]
    plant(a, 3, ["land_deed", "building_plan"], deed_value=10.00, plan_value=8.50)
    a["truth"]["land_area_acres"] = 10.00
    a["scan_docs"].add("building_plan")
    plant(a, 5, ["lab_photo"], source="archive_4417")
    a = by_id["EoA-DEMO-0422"]
    plant(a, 2, ["fire_noc"], printed_valid_till=date(2026, 3, 31))
    plant(a, 6, ["fire_noc"], qr_field="valid_till", qr_value=date(2027, 3, 31))
    a = by_id["EoA-DEMO-0431"]
    plant(a, 4, ["affidavit"], original=a["truth"]["aff_date"], edited=nosun(a["truth"]["aff_date"] + timedelta(days=61)))
    a["luc_no_channel"] = True
    a["luc_issuer_override"] = f"Demo Tehsil Office (Rural Block), {a['truth']['district']}"
    by_id["EoA-DEMO-0440"]["clean"] = True

    others = [x for x in apps if not x["hero"]]
    rng.shuffle(others)
    clean_n = 8
    for x in others[:clean_n]:
        x["clean"] = True
    defective = others[clean_n:]

    tasks = [1] * 5 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [6] * 4 + [7] * 5
    rng.shuffle(tasks)

    def eligible(app, dtype):
        if any(d["type"] == dtype for d in app["defects"]) or len(app["defects"]) >= 3:
            return False
        req = app["required"]
        if dtype == 2:
            return "fire_noc" not in app["docs_used"]
        if dtype == 3:
            return all(d in req and d not in app["docs_used"] for d in ("land_deed", "building_plan"))
        if dtype in (4, 7):
            return "affidavit" not in app["docs_used"]
        if dtype == 5:
            return "lab_photo" not in app["docs_used"]
        if dtype == 6:
            return any(d not in app["docs_used"] for d in QR_DOCS)
        return True

    # tasks 1 (missing doc) go last so they can pick any still-unused document
    sig_modes = ["unsigned", "unsigned", "unsigned", "broken", "broken"]
    rng.shuffle(sig_modes)
    ordered = [t for t in tasks if t != 1] + [1] * 5
    for t in ordered:
        pool = [x for x in defective if eligible(x, t)]
        pool.sort(key=lambda x: (len(x["defects"]), rng.random()))
        app = pool[0]
        if t == 1:
            free = [d for d in app["required"] if d not in app["docs_used"] and d not in ("land_deed", "building_plan", "affidavit")]
            plant(app, 1, [rng.choice(free)])
        elif t == 2:
            plant(app, 2, ["fire_noc"], printed_valid_till=date(2026, 1, 1) + timedelta(days=rng.randint(60, 170)))
        elif t == 3:
            true_area = app["truth"]["land_area_acres"]
            plant(app, 3, ["land_deed", "building_plan"], deed_value=true_area,
                  plan_value=round(true_area * rng.choice([0.78, 0.85, 0.9, 1.12, 1.2]), 2))
        elif t == 4:
            plant(app, 4, ["affidavit"], original=app["truth"]["aff_date"], edited=nosun(app["truth"]["aff_date"] + timedelta(days=rng.randint(20, 90))))
        elif t == 5:
            plant(app, 5, ["lab_photo"], source="archive")
        elif t == 6:
            doc = rng.choice([d for d in QR_DOCS if d not in app["docs_used"]])
            field = "certificate_no" if doc == "occupancy_cert" else rng.choice(["valid_till", "valid_till", "noc_no"])
            plant(app, 6, [doc], qr_field=field)
        elif t == 7:
            plant(app, 7, ["affidavit"], mode=sig_modes.pop())

    # duplicate faculty ids: 3 pairs (A's ids are copied into B's list)
    pairs = []
    pool = [x for x in apps if not x["hero"] and "faculty_list" not in x["docs_used"] and not x.get("clean")]
    pool += [x for x in apps if not x["hero"] and x.get("clean")][:0]
    rng.shuffle(pool)
    while len(pairs) < 3 and len(pool) >= 2:
        a1, b1 = pool.pop(), pool.pop()
        k = rng.randint(1, 2)
        shared = [dict(f) for f in a1["faculty"][:k]]
        b1["faculty"][-k:] = shared
        plant(a1, 8, ["faculty_list"], other=b1["id"], ids=[f["id"] for f in shared], role="source")
        plant(b1, 8, ["faculty_list"], other=a1["id"], ids=[f["id"] for f in shared], role="copy")
        pairs.append((a1["id"], b1["id"]))

    # realism: scans and Hindi pages
    scan_pool = ["land_deed", "building_plan", "land_use_cert", "fee_receipt", "faculty_list"]
    for x in apps:
        if x["id"] == "EoA-DEMO-0417" or x["hero"]:
            continue
        if rng.random() < 0.4:
            cand = [d for d in scan_pool if d in x["required"] and d not in x["docs_used"]]
            if cand:
                x["scan_docs"].add(rng.choice(cand))
    # make sure the hero 0422 / 0440 have no scans of QR docs (QR docs stay text) and 0440 gets one scan
    by_id["EoA-DEMO-0440"]["scan_docs"].add("fee_receipt")
    for i, x in enumerate(apps):
        x["hindi_page"] = (i % 5 == 0)

    # ---- real sample photos ------------------------------------------------------------------
    hero = by_id["EoA-DEMO-0417"]
    hero["real_slots"] = {"lab": ("full", "twin_a_physics_lab")}  # same room as archive #4417's twin_b, re-shot from another angle
    clean_nh = sorted((x for x in apps if x.get("clean") and not x["hero"]), key=lambda x: x["id"])
    # hard negatives: look-alike but different rooms, whole photos at institutions different from their look-alike's
    clean_nh[0]["real_slots"] = {"lab": ("full", "chem_lab_2")}
    clean_nh[1]["real_slots"] = {"lab": ("full", "lecture_hall_2")}
    cands = sorted((x for x in apps if not x["hero"] and not x.get("clean") and not any(d["type"] == 5 for d in x["defects"])), key=lambda x: x["id"])
    for perm, brightness in (("8115", +0.10), ("2208", -0.10), ("3375", +0.10), ("4926", -0.10)):  # 4 real "copy" twins
        slot, base = REAL_ARCHIVES[perm]
        doc = "lab_photo" if slot == "lab" else "building_photo"
        app = next(x for x in cands if doc not in x["docs_used"] and "real_slots" not in x)
        cands.remove(app)
        plant(app, 5, [doc], source="real_archive", real_source=perm, base=base, brightness=brightness, slot=slot)
    # background variety: non-overlapping halves (mirrored / colour-shifted) of the two small photos nobody else uses
    free = [x for x in apps if not x["hero"] and "real_slots" not in x]
    for slot, doc, base in (("lab", "lab_photo", "library_2"), ("building", "building_photo", "building_front_2")):
        pool = [x for x in free if doc not in x["docs_used"] and not any(d["type"] == 5 for d in x["defects"])][:4]
        for i, x in enumerate(pool):
            x.setdefault("real_slots", {})[slot] = ("half", base, i)
    # ---- shared land parcels (3), decoys (3) and impossible timelines (3) ------------------------
    nonhero = sorted((x for x in apps if not x["hero"]), key=lambda x: x["id"])
    defective_nh = [x for x in nonhero if not x.get("clean")]
    clean_nh2 = [x for x in nonhero if x.get("clean")]
    PARCEL = ("survey_no", "town", "district", "state", "region", "pincode", "address")
    claimants = [by_id["EoA-DEMO-0417"], defective_nh[2], defective_nh[5]]
    for claimant, owner in zip(claimants, clean_nh2[2:5]):  # the claimant files for land the (earlier) owner already filed
        for k in PARCEL:
            claimant["truth"][k] = owner["truth"][k]
        owner["submitted"] = min(owner["submitted"], claimant["submitted"] - timedelta(days=5))
        claimant["scan_docs"].discard("building_plan")
        plant(claimant, 9, ["building_plan"], owner=owner["id"], survey_no=owner["truth"]["survey_no"], village=owner["truth"]["town"])
    decoys = []
    for decoy, other in zip(clean_nh2[5:8], defective_nh[7:10]):  # same village, different plot: must NOT be flagged
        old = decoy["truth"]["town"]
        for k in ("town", "district", "state", "region", "pincode"):
            decoy["truth"][k] = other["truth"][k]
        decoy["truth"]["address"] = decoy["truth"]["address"].replace(old, other["truth"]["town"]).replace(decoy["truth"]["address"].split(",")[-1].strip(), other["truth"]["state"])
        assert decoy["truth"]["survey_no"] != other["truth"]["survey_no"]
        decoys.append({"application_id": decoy["id"], "village": other["truth"]["town"], "other_application": other["id"], "survey_no": decoy["truth"]["survey_no"],
                       "other_survey_no": other["truth"]["survey_no"]})
    t1 = by_id["EoA-DEMO-0422"]
    plant(t1, 10, ["fire_noc", "building_plan"], rule="fire_before_plan")
    t2 = next(x for x in defective_nh if not x["hero"] and "fire_noc" not in x["docs_used"] and "building_plan" not in x["docs_used"] and x not in claimants)
    t2["scan_docs"].discard("building_plan")
    plant(t2, 10, ["fire_noc", "building_plan"], rule="fire_before_plan")
    t3 = next(x for x in defective_nh if "occupancy_cert" not in x["docs_used"] and x is not t2 and x not in claimants)
    plant(t3, 10, ["occupancy_cert"], rule="sunday")
    return {"decoys": decoys, "apps": apps, "by_id": by_id, "pairs": pairs, "archives": ARCHIVES, "used_fac": used_fac}
