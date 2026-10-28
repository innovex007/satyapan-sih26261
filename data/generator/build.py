"""Renders every file for the world and assembles the answer key + mock registry."""
import copy
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

import imagehash

from . import pdfs, real
from .photos import (VARIANTS, VARIANT_JPEG_QUALITY, building_layout, derive_twin, lab_layout, make_variant, render_building, render_lab)
from .world import DEFECTS, REAL_ARCHIVES, SESSION_START, fmt, nosun

ARCHIVE_LABEL = "Archive · 2025 cycle"
PREVIOUS_LABEL = "Previous file · 2025 cycle"
FILE_NAMES = {
    "land_deed": ["Lease_Deed.pdf", "land_document_final.pdf"], "building_plan": ["Building_Plan.pdf", "approved_plan_v2.pdf"],
    "occupancy_cert": ["Occupancy_Certificate.pdf", "OC_copy.pdf"], "fire_noc": ["Fire_NOC.pdf", "fire_dept_noc.pdf"],
    "university_noc": ["University_NOC.pdf", "affiliation_letter.pdf"], "affidavit": ["Affidavit.pdf", "affidavit_signed.pdf"],
    "faculty_list": ["Faculty_List.pdf", "faculty_2026.pdf"], "fee_receipt": ["Fee_Receipt.pdf", "bank_receipt.pdf"],
    "land_use_cert": ["Land_Use_Conversion.pdf", "luc_certificate.pdf"],
}
IMAGE_TYPES = {"lab_photo": "Lab_Photo.jpg", "building_photo": "Building_Photo.jpg"}


def _shift_year(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _hashes(img):
    return imagehash.phash(img), imagehash.dhash(img), imagehash.whash(img)


class PhotoBank:
    """Keeps every photo's hashes so accidental near-duplicates across institutions (by pHash) are re-rolled."""

    def __init__(self):
        self.items: list[tuple[str, tuple]] = []  # (institution key, (phash, dhash, whash))

    def conflicts(self, inst: str, img) -> bool:
        h = _hashes(img)
        return any(i != inst and h[0] - o[0] <= 8 for i, o in self.items)

    def add(self, inst: str, img):
        self.items.append((inst, _hashes(img)))


def _fresh_room(rng, bank, inst, kind="lab", seed_base=0):
    for k in range(40):
        seed = seed_base + k * 7919 + rng.randint(0, 99999)
        if kind == "lab":
            L = lab_layout(random.Random(seed))
            img = render_lab(L, seed)
        else:
            L = building_layout(random.Random(seed))
            img = render_building(L, seed)
        if not bank.conflicts(inst, img):
            return L, seed, img
    raise RuntimeError("could not find a distinct room")


def _safe_lab(L, ls, inst, bank, dx, seed0, rot=0.0):
    """Same room, different camera position, re-rolled until it does not collide with another institution's image."""
    for k in range(14):
        img = render_lab({**L, "cam_dx": L["cam_dx"] + dx + 0.008 * k}, seed0 + k)
        if rot:
            img = img.rotate(rot)
        if not bank.conflicts(inst, img):
            bank.add(inst, img)
            return img
    raise RuntimeError("could not place a distinct variant")


def _best_twin(src, seed, good_enough=2):
    """Re-framed + brightened copy; search a grid for the copy a perceptual hash sees as closest."""
    best, h0 = None, imagehash.phash(src)
    for crop in (0.01, 0.006, 0.008, 0.012):
        for br in (1.02, 1.03, 1.04):
            for ns in range(8):
                tw = derive_twin(src, crop, br, seed * 10 + ns)
                d = h0 - imagehash.phash(tw)
                if best is None or d < best[0]:
                    best = (d, tw, crop, br)
                if best[0] <= good_enough:
                    return best
    return best


def build(world: dict, rules: dict, out_root: Path, seed: int) -> dict:
    rng = random.Random(seed + 1)
    groups = {k: v["group"] for k, v in rules["doc_types"].items()}
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)
    bank = PhotoBank()
    answer = {"seed": seed, "session_start": SESSION_START.isoformat(), "applications": [], "defects": [], "source_expectations": [],
              "last_year_applications": [], "hero_cases": []}
    registry: list[dict] = []
    ly_labs: dict[str, dict] = {}  # perm id -> {app,file,img,perm}  (archive-only institutions)

    def save(app_id, name, data: bytes) -> str:
        d = out_root / app_id
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(data)
        return f"files/{app_id}/{name}"

    # ------------------------------------------------------------------ last-year files (2025-26)
    def ly_truth(a):
        t = copy.deepcopy(a["truth"])
        t["fire_from"], t["fire_till"] = _shift_year(t["fire_from"], -1), _shift_year(t["fire_till"], -1)
        t["aff_date"], t["fee_date"] = _shift_year(t["aff_date"], -1), _shift_year(t["fee_date"], -1)
        t["deed_area"] = t["plan_area"] = t["land_area_acres"]
        t["deed_date_s"] = fmt(t["deed_date"])
        t["plan_date"] = nosun(t["deed_date"] + timedelta(days=100))
        t["faculty"] = copy.deepcopy(a["faculty"][:-2])
        t["luc_issuer"] = a["truth"]["luc_issuer"]
        return t

    def render_doc(doc_type, t, opts, fname, app_id, scan_seed=None, phone=False):
        r = pdfs.build_pdf(doc_type, t, opts)
        data, facts, extra = r["bytes"], r["facts"], {}
        sig = "none"
        if doc_type == "affidavit":
            mode = opts.get("sig_mode", "valid")
            if mode != "unsigned":
                data = pdfs.sign_pdf(data)
                sig = "valid"
            else:
                sig = "none"
            if opts.get("edited_date"):
                orig_t = pdfs.build_pdf("affidavit", t, {**opts, "edited_date": None})
                signed = pdfs.sign_pdf(orig_t["bytes"])
                data = pdfs.edit_after_signing(signed, r["bytes"])
                sig = "modified_after_signing"
            elif mode == "broken":
                old = fmt(t["aff_date"])
                new = old[:-1] + ("7" if old[-1] != "7" else "8")
                data = pdfs.tamper_signed(data, old, new)
                for f in facts:
                    if f["key"] == "affidavit_date":
                        f["value"], f["normalised"] = new, "-".join(reversed(new.split("-")))
                sig = "broken"
        kind = "text"
        if scan_seed is not None:
            data, facts, extra = pdfs.make_scan(data, facts, scan_seed, phone)
            kind = "scan"
        path = save(app_id, fname, data)
        return {"file": fname, "path": path, "doc_type": doc_type, "group": groups[doc_type], "kind": kind, "pages": r["pages"],
                "facts": facts, "qr": r.get("qr"), "issuer": r.get("issuer"), "signature": sig, "scan": extra or None}

    def photo_doc(app_id, doc_type, fname, img, extra=None, quality=88, raw_bytes=None):
        path = save(app_id, fname, raw_bytes if raw_bytes is not None else pdfs.image_to_jpeg(img, quality))
        return {"file": fname, "path": path, "doc_type": doc_type, "group": groups[doc_type], "kind": "image", "pages": 1,
                "facts": [], "qr": None, "issuer": None, "signature": "none", "scan": None, **(extra or {})}

    # archive-only institutions (#4417 and friends): a 2025 lab + building photo each; some hold a REAL sample photo
    for arch in world["archives"]:
        arch_id = f"EoA-2025-{arch['perm']}"
        _, _, aimg = _fresh_room(rng, bank, arch["perm"], "lab", int(arch["perm"]))
        _, _, bimg = _fresh_room(rng, bank, arch["perm"], "building", int(arch["perm"]) + 1)
        meta = {"lab": {}, "building": {}}
        raws = {"lab": None, "building": None}
        if arch["perm"] in REAL_ARCHIVES:
            slot, base = REAL_ARCHIVES[arch["perm"]]
            im = real.image(base)
            if slot == "lab":
                aimg = im
            else:
                bimg = im
            raws[slot], meta[slot] = real.raw(base), {"real_photo": base}
        bank.add(arch["perm"], aimg)
        bank.add(arch["perm"], bimg)
        answer["last_year_applications"].append({
            "id": arch_id, "institution": arch["name"], "permanent_id": arch["perm"], "archive_only": True, "session": "2025-26",
            "cycle_label": ARCHIVE_LABEL,
            "documents": [photo_doc(arch_id, "lab_photo", "Lab_Photo.jpg", aimg, meta["lab"], raw_bytes=raws["lab"]),
                          photo_doc(arch_id, "building_photo", "Building_Photo.jpg", bimg, meta["building"], raw_bytes=raws["building"])]})
        slot = REAL_ARCHIVES.get(arch["perm"], ("lab",))[0]
        ly_labs[arch["perm"]] = {"app": arch_id, "file": "Building_Photo.jpg" if slot == "building" else "Lab_Photo.jpg",
                                 "img": bimg if slot == "building" else aimg, "perm": arch["perm"]}
    lab_rooms = {}

    for a in world["apps"]:
        t0 = a["truth"]
        L, ls, limg = _fresh_room(rng, bank, a["id"], "lab", t0["serial"] * 31)
        bank.add(a["id"], limg)
        _, _, bphoto = _fresh_room(rng, bank, a["id"], "building", t0["serial"] * 13 + 5)
        bank.add(a["id"], bphoto)
        a["_bphoto"] = bphoto
        prev, cur = limg, limg
        if a["has_last_year"]:  # same room photographed again a year later: legitimate, same institution
            prev = _safe_lab(L, ls, a["id"], bank, -0.03, ls + 1)
            cur = _safe_lab(L, ls, a["id"], bank, 0.02, ls + 2)
        a["_lab_raw"], a["_b_raw"], a["_lab_meta"], a["_b_meta"] = None, None, {}, {}
        for slot, spec in a.get("real_slots", {}).items():  # real sample photo for this institution
            im = real.image(spec[1]) if spec[0] == "full" else real.half_variant(spec[1], spec[2])
            raw_b = real.raw(spec[1]) if spec[0] == "full" else None
            meta = {"real_photo": spec[1], "real_mode": spec[0] if spec[0] == "full" else f"half-{spec[2]}"}
            bank.add(a["id"], im)
            if slot == "lab":
                cur, a["_lab_raw"], a["_lab_meta"] = im, raw_b, meta
            else:
                a["_bphoto"], a["_b_raw"], a["_b_meta"] = im, raw_b, meta
        lab_rooms[a["id"]] = (L, ls, cur, prev)

    for a in world["apps"]:
        if not a["has_last_year"]:
            continue
        t = ly_truth(a)
        app_id = f"EoA-2025-{a['perm']}"
        docs = []
        for dt in ("land_deed", "building_plan", "fire_noc", "affidavit", "faculty_list"):
            if dt == "land_deed" and "land_deed" not in a["required"]:
                continue
            fname = FILE_NAMES[dt][0]
            docs.append(render_doc(dt, t, {"sig_mode": "valid"}, fname, app_id))
        L, ls, cur, prev = lab_rooms[a["id"]]
        docs.append(photo_doc(app_id, "lab_photo", "Lab_Photo.jpg", prev))
        docs.append(photo_doc(app_id, "building_photo", "Building_Photo.jpg", a["_bphoto"].rotate(0.4)))
        answer["last_year_applications"].append({"id": app_id, "institution": a["truth"]["institution_name"], "permanent_id": a["perm"],
                                                 "archive_only": False, "session": "2025-26", "cycle_label": PREVIOUS_LABEL, "for_application": a["id"], "documents": docs})

    # ------------------------------------------------------------------ current applications
    defect_seq = 0
    twin_report = []
    used_sources: set = set()
    for a in world["apps"]:
        t = copy.deepcopy(a["truth"])
        t["faculty"] = a["faculty"]
        t["deed_area"] = t["plan_area"] = t["land_area_acres"]
        t["deed_date_s"] = fmt(t["deed_date"])
        t["plan_date"] = nosun(t["deed_date"] + timedelta(days=100))
        missing, doc_defects = [], {}
        for d in a["defects"]:
            for dt in d["docs"]:
                doc_defects.setdefault(dt, []).append(d)
            if d["type"] == 1:
                missing = d["docs"]
            if d["type"] == 2:
                t["fire_till"] = d["detail"]["printed_valid_till"]
                t["fire_from"] = nosun(_shift_year(t["fire_till"], -1) + timedelta(days=1))
            if d["type"] == 3:
                t["deed_area"], t["plan_area"] = d["detail"]["deed_value"], d["detail"]["plan_value"]
        for d in a["defects"]:  # planted timelines (computed once the final Fire NOC date is known)
            if d["type"] == 10 and d["detail"]["rule"] == "fire_before_plan":
                t["plan_date"] = nosun(t["fire_from"] + timedelta(days=45))
                d["detail"].update(fire_noc_issued=t["fire_from"], plan_approved=t["plan_date"])
            if d["type"] == 10 and d["detail"]["rule"] == "sunday":
                while t["oc_date"].weekday() != 6:
                    t["oc_date"] += timedelta(days=1)
                d["detail"].update(date=t["oc_date"])
        if a.get("luc_issuer_override"):
            t["luc_issuer"] = a["luc_issuer_override"]
        docs = []
        for k, dt in enumerate(a["required"]):
            if dt in missing:
                continue
            ds = doc_defects.get(dt, [])
            opts = {"hindi": a["hindi_page"] and dt == "affidavit"}
            for d in ds:
                if d["type"] == 6:
                    opts["qr_field"] = d["detail"]["qr_field"]
                    if "qr_value" in d["detail"]:
                        opts["qr_value"] = d["detail"]["qr_value"]
                if d["type"] == 4:
                    opts["edited_date"] = d["detail"]["edited"]
                if d["type"] == 7:
                    opts["sig_mode"] = d["detail"]["mode"]
            if dt in IMAGE_TYPES:
                continue
            scan = dt in a["scan_docs"]
            fname = f"scan_{rng.randint(1000, 9999)}.pdf" if scan else rng.choice(FILE_NAMES[dt])
            docs.append(render_doc(dt, t, opts, fname, a["id"], scan_seed=(t["serial"] * 100 + k) if scan else None,
                                   phone=scan and rng.random() < 0.5))

        # photos -------------------------------------------------
        L, ls, lab_img, _prev = lab_rooms[a["id"]]
        b_img, lab_q, b_q = a["_bphoto"], 88, 88
        lab_raw, b_raw, lab_meta, b_meta = a["_lab_raw"], a["_b_raw"], dict(a["_lab_meta"]), dict(a["_b_meta"])
        for td in [d for d in a["defects"] if d["type"] == 5]:
            det = td["detail"]
            if det["source"] == "archive_4417":  # the hero: twin_a (this app) vs twin_b (archive #4417): same room, re-shot
                src = ly_labs["4417"]
                det.update(source_application=src["app"], source_file=src["file"], twin_kind="reshot", difficulty="hard",
                           phash_distance=int(imagehash.phash(lab_img) - imagehash.phash(src["img"])))
            elif det["source"] == "real_archive":  # real photo copied from an archive file: 4% crop, +/-10% brightness, JPEG q70
                src = ly_labs[det["real_source"]]
                cp = real.copy_variant(src["img"], det["brightness"])
                if det["slot"] == "lab":
                    lab_img, lab_q, lab_raw, lab_meta = cp, 70, None, {"real_photo": det["base"], "real_mode": "copy"}
                else:
                    b_img, b_q, b_raw, b_meta = cp, 70, None, {"real_photo": det["base"], "real_mode": "copy"}
                det.update(source_application=src["app"], source_file=src["file"], twin_kind="copy", difficulty="medium", crop_pct=4,
                           jpeg_quality=70, phash_distance=int(imagehash.phash(cp) - imagehash.phash(src["img"])))
            else:  # drawn-room copy of an archive file (earlier twin set)
                src = next(v for k2, v in ly_labs.items() if k2 not in used_sources and k2 != "4417")
                used_sources.add(src["perm"])
                dist, lab_img, crop, br = _best_twin(src["img"], t["serial"], good_enough=4)
                det.update(source_application=src["app"], source_file=src["file"], phash_distance=int(dist), crop=crop, brightness=br,
                           twin_kind="copy", difficulty="easy")
            twin_report.append((a["id"], det["source_application"], det["phash_distance"]))
        if "lab_photo" not in missing:
            docs.append(photo_doc(a["id"], "lab_photo", IMAGE_TYPES["lab_photo"], lab_img, lab_meta, quality=lab_q, raw_bytes=lab_raw))
        if "building_photo" not in missing:
            docs.append(photo_doc(a["id"], "building_photo", IMAGE_TYPES["building_photo"], b_img, b_meta, quality=b_q, raw_bytes=b_raw))
        extra_def = None

        # two frames from a 'lab video' of the same room
        for fi, pan in enumerate((-0.02, 0.025), 1):
            frame = _safe_lab(L, ls, a["id"], bank, pan, ls + 10 + fi * 20, rot=0.3 * fi)
            docs.append(photo_doc(a["id"], "lab_video_frame", f"lab_video_frame_{fi}.jpg", frame, {"video": "Lab_Walkthrough.mp4 (frame)"}))

        # registry (mock issuer / DigiLocker records hold the TRUE values) -----------
        for d in docs:
            if d["doc_type"] == "fire_noc":
                registry.append({"channel": "issuer_portal", "doc_type": "fire_noc", "number": t["fire_no"], "institution": t["institution_name"],
                                 "issuer": d["issuer"], "valid_from": t["fire_from"].isoformat(), "valid_till": t["fire_till"].isoformat(), "status": "active"})
            elif d["doc_type"] == "occupancy_cert":
                registry.append({"channel": "issuer_portal", "doc_type": "occupancy_cert", "number": t["oc_no"], "institution": t["institution_name"],
                                 "issuer": d["issuer"], "issue_date": t["oc_date"].isoformat(), "status": "active"})
            elif d["doc_type"] == "university_noc":
                registry.append({"channel": "digilocker", "doc_type": "university_noc", "number": t["univ_no"], "institution": t["institution_name"],
                                 "issuer": d["issuer"], "valid_till": t["univ_till"].isoformat(), "status": "active"})
            elif d["doc_type"] == "land_use_cert" and not a.get("luc_no_channel"):
                registry.append({"channel": "issuer_portal", "doc_type": "land_use_cert", "number": t["luc_no"], "institution": t["institution_name"],
                                 "issuer": d["issuer"], "issue_date": t["luc_date"].isoformat(), "status": "active"})

        # source expectations ---------------------------------------------------------
        qr_bad = {dt for d in a["defects"] if d["type"] == 6 for dt in d["docs"]}
        for d in docs:
            routes = rules["source_routing"].get(d["doc_type"], [])
            for ch in routes:
                if ch == "qr":
                    exp = "Mismatch detected" if d["doc_type"] in qr_bad else "Verified"
                elif ch == "signature":
                    exp = "Verified" if d["signature"] == "valid" else "Manual review required"
                elif d["doc_type"] == "land_use_cert" and a.get("luc_no_channel"):
                    exp, ch = "Source unavailable", "letter"
                else:
                    exp = "Verified"
                answer["source_expectations"].append({"application_id": a["id"], "document": d["file"], "doc_type": d["doc_type"],
                                                      "channel": ch, "expected_status": exp})

        # defects -> answer key ---------------------------------------------------------
        by_type_docs = {d["doc_type"]: d for d in docs if d["file"] != "Lab_Photo_2.jpg"}
        if extra_def:
            defect_seq += 1
            answer["defects"].append({"id": f"D{defect_seq:03d}", "type_id": 5, "type": DEFECTS[5][0], "application_id": a["id"],
                                      "document": "Lab_Photo_2.jpg", "doc_type": "lab_photo", "expected_status": DEFECTS[5][1],
                                      "expected_check": "twin", "detail": extra_def, "hero": False, "extra_set": True,
                                      "difficulty": extra_def["difficulty"]})
        for d in a["defects"]:
            defect_seq += 1
            name, status, check = DEFECTS[d["type"]]
            det = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d["detail"].items()}
            files = [by_type_docs[dt]["file"] for dt in d["docs"] if dt in by_type_docs]
            answer["defects"].append({
                "id": f"D{defect_seq:03d}", "type_id": d["type"], "type": name, "application_id": a["id"],
                "document": files[0] if len(files) == 1 else (files or None),
                "doc_type": d["docs"][0] if len(d["docs"]) == 1 else d["docs"],
                "expected_status": status, "expected_check": check, "detail": det, "hero": a["hero"],
                "difficulty": d["detail"].get("difficulty") if d["type"] == 5 else None})
        answer["applications"].append({
            "id": a["id"], "hero": a["hero"], "clean": bool(a.get("clean")), "institution": t["institution_name"], "permanent_id": a["perm"],
            "category": a["category"], "region": t["region"], "state": t["state"], "required": a["required"], "missing": missing,
            "has_last_year_file": a["has_last_year"], "scan_documents": [d["file"] for d in docs if d["kind"] == "scan"],
            "documents": docs})
    answer["decoys"] = world["decoys"]
    answer["mock_registry_count"] = len(registry)
    answer["twin_pairs"] = twin_report
    return {"answer": answer, "registry": registry}
