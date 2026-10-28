"""All checks for one application -> Findings + SourceChecks, then the risk lane.
Rule ids: CHK-* are document checks, SRC-* are (simulated) source checks. Thresholds come from the rule file."""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import imagehash
import pdfplumber
from sqlmodel import Session, select

from ...core.config import STORAGE_DIR
from ...models import Application, Document, Fact, Finding, ImageFingerprint, Institution, SourceCheck
from ...rules.loader import load_rules
from ..sources import simulated as sim

RULESET = "APH-2026-27"
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _sq(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _dmy(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d-%m-%Y")
    except ValueError:
        return iso


class Ctx:
    def __init__(self, s: Session, app: Application):
        self.s, self.app, self.rules = s, app, load_rules()
        self.inst = s.get(Institution, app.institution_id)
        self.docs = s.exec(select(Document).where(Document.application_id == app.id)).all()
        self.facts: dict[int, dict[str, list[Fact]]] = {}
        for f in s.exec(select(Fact).where(Fact.document_id.in_([d.id for d in self.docs]))).all() if self.docs else []:
            self.facts.setdefault(f.document_id, {}).setdefault(f.key, []).append(f)
        self.findings: list[Finding] = []

    def fact(self, doc: Document, key: str) -> Fact | None:
        return (self.facts.get(doc.id, {}).get(key) or [None])[0]

    def of_type(self, t: str) -> list[Document]:
        return [d for d in self.docs if d.doc_type == t]

    def ev(self, doc: Document, fact: Fact | None = None, value: str | None = None, **extra) -> dict:
        return {"document_id": doc.id, "filename": doc.filename, "doc_type": doc.doc_type, "page": fact.page if fact else 1,
                "bbox": list(fact.bbox) if fact else [], "value": value if value is not None else (fact.value if fact else ""),
                "key": fact.key if fact else None, "normalised": fact.normalised_value if fact else None, **extra}

    def add(self, check_type, status, severity, conf, reason, rule_id, evidence, how, docs=()):
        self.findings.append(Finding(application_id=self.app.id, document_ids=[d.id for d in docs], check_type=check_type, status=status,
                                     severity=severity, confidence=round(conf, 2), reason=reason, rule_id=f"{RULESET}/{rule_id}",
                                     evidence=evidence, how_to_clear=how))


# ---------------------------------------------------------------------------------------------
def check_completeness(c: Ctx):
    present = {d.doc_type for d in c.docs}
    for t in c.rules["categories"][c.app.category]["required"]:
        if t not in present:
            label = c.rules["doc_types"][t]["label"]
            c.add("completeness", "Verification pending", "high", 0.99, f"Missing document: {label} is required for '{c.app.category}' but was not uploaded.",
                  "CHK-COMPLETE-01", [{"document_id": None, "filename": None, "doc_type": t, "page": 1, "bbox": [], "value": "missing"}],
                  f"Clears when the {label} is uploaded.")


def check_expiry(c: Ctx):
    start = c.rules["session"]["start"]
    start = start if isinstance(start, date) else date.fromisoformat(str(start))
    for t in ("fire_noc", "university_noc"):
        for d in c.of_type(t):
            f = c.fact(d, "valid_till")
            if not f:
                continue
            try:
                till = date.fromisoformat(f.normalised_value)
            except ValueError:
                continue
            if till < start:
                label = c.rules["doc_types"][t]["label"]
                c.add("expiry", "Expired", "high", 0.97 * min(1.0, f.confidence + 0.05),
                      f"{label} is valid till {_dmy(f.normalised_value)}, before the session starts on {_dmy(start.isoformat())}.", "CHK-EXPIRY-01",
                      [c.ev(d, f)], f"Clears if a {label} valid beyond {_dmy(start.isoformat())} is uploaded.", [d])


def _consensus(entries, tol_pct=None):
    """Group (doc, fact, number|text) entries; reference = largest agreeing group, ties broken by document order."""
    groups: list[list] = []
    for e in entries:
        for g in groups:
            ref = g[0][2]
            ok = (abs(e[2] - ref) <= abs(ref) * tol_pct / 100) if tol_pct is not None else _sq(e[2]) == _sq(ref)
            if ok:
                g.append(e)
                break
        else:
            groups.append([e])
    groups.sort(key=lambda g: -len(g))
    return groups


def check_contradictions(c: Ctx):
    tol = c.rules["tolerances"]["land_area_pct"]
    order = {"land_deed": 0, "land_use_cert": 1, "occupancy_cert": 2, "building_plan": 3}
    for key, kind, rid, label in (("land_area_acres", "area", "CHK-XDOC-LAND-01", "Land area"), ("survey_no", "text", "CHK-XDOC-SURVEY-01", "Survey number")):
        entries = []
        for d in sorted(c.docs, key=lambda d: order.get(d.doc_type, 9)):
            f = c.fact(d, key)
            if f:
                try:
                    entries.append((d, f, float(f.normalised_value) if kind == "area" else f.normalised_value))
                except ValueError:
                    pass
        if len(entries) < 2:
            continue
        groups = _consensus(entries, tol if kind == "area" else None)
        if len(groups) > 1:
            ref, others = groups[0][0], [e for g in groups[1:] for e in g]
            ev = [c.ev(ref[0], ref[1])] + [c.ev(o[0], o[1]) for o in others]
            names = lambda e: c.rules["doc_types"][e[0].doc_type]["label"]  # noqa: E731
            if kind == "area":
                diff = abs(others[0][2] - ref[2]) / ref[2] * 100
                reason = (f"Land area differs between documents: {names(ref)} shows {ref[2]:.2f} acres, {names(others[0])} shows {others[0][2]:.2f} acres "
                          f"({diff:.1f}% apart, tolerance ±{tol}%).")
                how = f"Clears if the {names(others[0])} shows a plot area of {ref[2]:.2f} ± {ref[2] * tol / 100:.2f} acres (or the {names(ref)} is corrected)."
            else:
                reason = f"Survey number differs: {names(ref)} shows '{ref[1].value}', {names(others[0])} shows '{others[0][1].value}'."
                how = f"Clears if all documents carry the same survey number ('{ref[1].value}')."
            conf = min(e[1].confidence for e in entries) * 0.97
            c.add("contradiction", "Mismatch detected", "high", conf, reason, rid, ev, how, [e[0] for e in [ref] + others])
        else:  # documents agree with each other: compare with last year's file
            ly = c.s.get(Application, f"EoA-2025-{c.inst.permanent_id}")
            if not ly:
                continue
            for d in c.s.exec(select(Document).where(Document.application_id == ly.id)).all():
                f = c.s.exec(select(Fact).where(Fact.document_id == d.id, Fact.key == key)).first()
                if not f:
                    continue
                cur = groups[0][0]
                same = (abs(float(f.normalised_value) - cur[2]) <= cur[2] * tol / 100) if kind == "area" else _sq(f.normalised_value) == _sq(cur[2])
                if not same:
                    c.add("contradiction", "Mismatch detected", "medium", 0.8 * cur[1].confidence,
                          f"{label} in this application ({cur[1].value}) differs from last year's file ({f.value}).", rid.replace("XDOC", "XYEAR"),
                          [c.ev(cur[0], cur[1]), {"document_id": d.id, "filename": d.filename, "doc_type": d.doc_type, "page": f.page, "bbox": list(f.bbox),
                                                  "value": f.value, "cycle": "2025"}],
                          f"Clears if the change in {label.lower()} since last year is explained by a supporting document.", [cur[0]])
                break


def check_twins(c: Ctx):
    """Stage 1: pHash <= hash_flag_max = copy. Stage 2: pHash <= hash_candidate_max, ORB+RANSAC verified = same room re-shot."""
    from .. import similarity as simg

    tc = c.rules["twin"]
    imgs = [d for d in c.docs if d.kind == "image"]
    if not imgs:
        return
    mine = {fp.document_id: fp for fp in c.s.exec(select(ImageFingerprint).where(ImageFingerprint.document_id.in_([d.id for d in imgs]))).all()}
    others = c.s.exec(select(ImageFingerprint, Document).join(Document, Document.id == ImageFingerprint.document_id)
                      .where(ImageFingerprint.institution_id != c.app.institution_id)).all()
    for d in imgs:
        fp = mine.get(d.id)
        if not fp:
            continue
        best = None  # (rank, other doc, result)
        for ofp, od in others:
            res = simg.compare(fp.phash, ofp.phash, STORAGE_DIR / d.file_path, STORAGE_DIR / od.file_path, tc, simg.orb_applies(d.doc_type, od.doc_type))
            if not res["twin"]:
                continue
            rank = (0, res["phash_distance"]) if res["kind"] == "copy" else (1, -res["orb"]["inliers"])
            if best is None or rank < best[0]:
                best = (rank, od, res)
        if best is None:
            continue
        _, od, res = best
        oa = c.s.get(Application, od.application_id)
        oi = c.s.get(Institution, oa.institution_id)
        label = c.rules["doc_types"].get(d.doc_type, {}).get("label", "Photo")
        who = f"{oa.cycle_label.lower()} file of {oi.name} (#{oi.permanent_id}), a different institution"
        if res["kind"] == "copy":
            detail = f"is a copied photo (an edited copy; pHash distance {res['phash_distance']}) of an image in the {who}."
            conf, val = 0.99 - res["phash_distance"] * 0.01, f"copy · pHash distance {res['phash_distance']}"
        else:
            n = res["orb"]["inliers"]
            detail = (f"shows the same room as an image in the {who}, re-photographed from another angle ({n} keypoint matches, threshold "
                      f"{tc['orb']['min_inliers']}; pHash distance {res['phash_distance']}, so a hash alone would miss it).")
            conf, val = min(0.97, 0.7 + n / 400), f"same room, re-shot · {n} matched keypoints"
        c.add("twin", "Manual review required", "high", conf, f"{label} '{d.filename}' {detail}", "CHK-TWIN-01",
              [c.ev(d, None, val, twin_kind=res["kind"], phash_distance=res["phash_distance"], inliers=(res["orb"] or {}).get("inliers")),
               {"document_id": od.id, "filename": od.filename, "doc_type": od.doc_type, "page": 1, "bbox": [],
                "value": f"{oi.name} (#{oi.permanent_id}) · {oa.cycle_label}", "application_id": oa.id}],
              "Clears if the officer confirms the photo was taken at this institution, or an original dated photograph is uploaded.", [d, od])


LAND_DOCS = ("land_deed", "land_use_cert", "building_plan")


def check_shared_land(c: Ctx):
    """NEW: the same survey number + village in the land documents of two different institutions. The later filer is flagged."""
    mine = []
    for t in LAND_DOCS:
        for d in c.of_type(t):
            s_, v_ = c.fact(d, "survey_no"), c.fact(d, "village")
            if s_ and v_:
                mine.append((d, s_, v_))
    if not mine:
        return
    wanted = {_sq(s_.normalised_value): (d, s_, v_) for d, s_, v_ in reversed(mine)}
    rows = c.s.exec(select(Fact, Document, Application).join(Document, Document.id == Fact.document_id)
                    .join(Application, Application.id == Document.application_id)
                    .where(Fact.key == "survey_no", Application.academic_session == "2026-27", Application.institution_id != c.app.institution_id,
                           Document.doc_type.in_(LAND_DOCS))).all()
    for of, od, oa in rows:
        hit = wanted.get(_sq(of.normalised_value))
        if not hit:
            continue
        md, ms, mv = hit
        ov = c.s.exec(select(Fact).where(Fact.document_id == od.id, Fact.key == "village")).first()
        if not ov or _sq(ov.normalised_value) != _sq(mv.normalised_value):
            continue  # same plot number in a different village: a decoy, not a shared parcel
        if (oa.submitted_at, oa.id) > (c.app.submitted_at, c.app.id):
            continue  # the earlier filer is the owner; only the later one is flagged
        oi = c.s.get(Institution, oa.institution_id)
        c.add("contradiction", "Manual review required", "high", 0.9 * min(ms.confidence, of.confidence),
              f"Same land parcel (Survey {ms.value}, Village {mv.value}) also claimed by {oi.name} ({oa.id}).", "CHK-SHAREDLAND-01",
              [c.ev(md, ms), c.ev(od, of, application_id=oa.id), c.ev(md, mv), c.ev(od, ov, application_id=oa.id)],
              "Clears if the institution shows title or a lease for this parcel (the other claim is verified separately), or corrects the survey details.", [md, od])
        return


KEY_WORDS = {"deed_date": "deed date", "issue_date": "issue date", "valid_from": "issue date", "receipt_date": "receipt date",
             "affidavit_date": "signing date", "approval_date": "approval date"}


def _iso(f):
    try:
        return date.fromisoformat(f.normalised_value) if f else None
    except ValueError:
        return None


def check_timeline(c: Ctx):
    """NEW: two rules from the rule file: Fire NOC issued before the plan was approved; issue/signing dates on a Sunday."""
    tl = c.rules.get("timeline", {})
    if tl.get("fire_noc_not_before_plan_approval"):
        for fd in c.of_type("fire_noc"):
            for pd in c.of_type("building_plan"):
                ff, pf = c.fact(fd, "valid_from"), c.fact(pd, "approval_date")
                a, b = _iso(ff), _iso(pf)
                if a and b and a < b:
                    c.add("contradiction", "Mismatch detected", "high", 0.93 * min(ff.confidence, pf.confidence),
                          f"Fire NOC was issued on {a:%d-%m-%Y}, before the building plan was approved on {b:%d-%m-%Y}.", "CHK-TIMELINE-01",
                          [c.ev(fd, ff), c.ev(pd, pf)], "Clears if the Fire NOC issue date is on or after the plan approval date, or a corrected certificate is uploaded.", [fd, pd])
    if tl.get("no_sunday_issue_dates"):
        for d in c.docs:
            for key in tl.get("issue_date_keys", []):
                f = c.fact(d, key)
                dt = _iso(f)
                if dt and dt.weekday() == 6:
                    label = c.rules["doc_types"].get(d.doc_type, {}).get("label", d.doc_type)
                    c.add("contradiction", "Mismatch detected", "medium", 0.9 * f.confidence,
                          f"The {label} {KEY_WORDS.get(key, key)} is {dt:%d-%m-%Y}, which is a Sunday (issuing offices are closed).", "CHK-TIMELINE-02",
                          [c.ev(d, f)], "Clears if the issuing office confirms the date, or a corrected document is uploaded.", [d])


def _fonts_at(pdf_path: Path, bbox) -> set:
    with pdfplumber.open(pdf_path) as pdf:
        pg = pdf.pages[0]
        w, h = float(pg.width), float(pg.height)
        box = (bbox[0] * w, bbox[1] * h, bbox[2] * w, bbox[3] * h)
        return {(ch["fontname"].split("+")[-1], round(ch["size"])) for ch in pg.chars
                if box[0] <= (ch["x0"] + ch["x1"]) / 2 <= box[2] and box[1] <= (ch["top"] + ch["bottom"]) / 2 <= box[3]}


def check_forensics(c: Ctx):
    for d in c.of_type("affidavit"):
        if d.kind != "text":
            continue
        path = STORAGE_DIR / d.file_path
        info = sim.signature_state(path)
        signals = []
        if info["state"] == "modified_after_signing":
            signals.append(f"incremental save after signing ({info['revisions']} revisions)")
        if info["producer"] and re.search(r"editor", info["producer"], re.I):
            signals.append(f"editing software in metadata ({info['producer']})")
        date_f = c.fact(d, "affidavit_date")
        if date_f:
            others = [c.fact(d, k) for k in ("institution_name", "signatory")]
            ref = set().union(*[_fonts_at(path, o.bbox) for o in others if o]) if any(others) else set()
            mine = _fonts_at(path, date_f.bbox)
            if ref and mine and not (mine & ref):
                signals.append(f"font outlier in the date field ({', '.join(f'{n} {s}pt' for n, s in sorted(mine))})")
        if len(signals) >= c.rules["forensics"]["min_independent_signals"] and info["state"] == "modified_after_signing":
            c.add("forensic", "Manual review required", "high", min(0.95, 0.5 + 0.15 * len(signals)),
                  f"Preliminary indicator: {len(signals)} independent signal(s) on the affidavit: " + "; ".join(signals) + ". Manual review required.",
                  "CHK-FORENSIC-01", [c.ev(d, date_f)] if date_f else [c.ev(d)],
                  "Clears if the institution supplies the originally signed affidavit, or the officer confirms the edit was authorised.", [d])


def check_faculty(c: Ctx):
    mine = {}
    for d in c.of_type("faculty_list"):
        for f in c.facts.get(d.id, {}).get("faculty_id", []):
            mine[f.normalised_value] = (d, f)
    if not mine:
        return
    rows = c.s.exec(select(Fact, Document, Application).join(Document, Document.id == Fact.document_id)
                    .join(Application, Application.id == Document.application_id)
                    .where(Fact.key == "faculty_id", Application.academic_session == "2026-27", Application.institution_id != c.app.institution_id,
                           Fact.normalised_value.in_(list(mine)))).all()
    by_id: dict[str, list] = {}
    for f, d2, a2 in rows:
        by_id.setdefault(f.normalised_value, []).append((d2, a2))
    for fid, hits in by_id.items():
        d, f = mine[fid]
        a2 = hits[0][1]
        i2 = c.s.get(Institution, a2.institution_id)
        c.add("faculty", "Manual review required", "medium", 0.9,
              f"Faculty ID {f.value} also appears in the faculty list of {i2.name} ({a2.id}) in this cycle.", "CHK-FACULTY-01",
              [c.ev(d, f), {"document_id": hits[0][0].id, "filename": hits[0][0].filename, "doc_type": "faculty_list", "page": 1, "bbox": [],
                            "value": f"{f.value} in {a2.id}", "application_id": a2.id}],
              "Clears if the faculty member's employment at only one institution is confirmed (e.g. relieving letter).", [d])


# ---------------------------------------------------------------------------------------------
def check_sources(c: Ctx):
    registry = sim.load_registry()
    offline = c.rules["source"]["no_online_channel_issuers"]

    def row(d, channel, result, response):
        c.s.add(SourceCheck(document_id=d.id, channel=channel, response=response, result=result, simulated=True))

    for d in c.docs:
        if d.kind != "text" and d.doc_type not in ("land_use_cert", "fire_noc", "occupancy_cert", "university_noc"):
            continue
        path = STORAGE_DIR / d.file_path
        label = c.rules["doc_types"].get(d.doc_type, {}).get("label", d.doc_type)
        num_f = c.fact(d, "noc_number") or c.fact(d, "certificate_no")
        # --- QR vs printed
        if "qr" in c.rules["source_routing"].get(d.doc_type, []) and d.kind == "text":
            qr = sim.decode_qr(path)
            if qr is None:
                row(d, "qr", "Verification pending", {"note": "QR not readable"})
            else:
                diffs = []
                if num_f and _sq(qr.get("noc_no") or qr.get("certificate_no") or "") != _sq(num_f.value):
                    diffs.append(("number", qr.get("noc_no") or qr.get("certificate_no"), num_f))
                vf = c.fact(d, "valid_till")
                if vf and qr.get("valid_till") and qr["valid_till"] != vf.normalised_value:
                    diffs.append(("validity", qr["valid_till"], vf))
                if diffs:
                    what, qv, pf = diffs[0]
                    row(d, "qr", "Mismatch detected", {"qr": qr, "printed": pf.value})
                    printed = _dmy(pf.normalised_value) if what == "validity" else pf.value
                    shown = _dmy(qv) if what == "validity" else qv
                    c.add("source", "Mismatch detected", "high", 0.96, f"QR code on the {label} carries {what} '{shown}' but the printed text shows '{printed}'.",
                          "SRC-QR-01", [c.ev(d, pf)], f"Clears if the QR code and the printed {what} on the {label} agree (re-issue from the issuing office).", [d])
                else:
                    row(d, "qr", "Verified", {"qr": qr})
        # --- signature
        if "signature" in c.rules["source_routing"].get(d.doc_type, []) and d.kind == "text":
            st = sim.signature_state(path)["state"]
            res = "Verified" if st == "valid" else "Manual review required"
            row(d, "signature", res, {"state": st})
            if st in ("none", "broken"):
                what = "carries no digital signature" if st == "none" else "has a digital signature that no longer verifies (content changed after signing)"
                c.add("source", "Manual review required", "high", 0.9, f"The {label} {what}.", "SRC-SIG-01", [c.ev(d, c.fact(d, "affidavit_date"))],
                      "Clears if the institution uploads the affidavit with a valid digital signature.", [d])
        # --- issuer portal / DigiLocker (simulated registry)
        chans = [x for x in c.rules["source_routing"].get(d.doc_type, []) if x in ("issuer_portal", "digilocker")]
        if chans:
            issuer_f = c.fact(d, "issuer")
            issuer_txt = issuer_f.value if issuer_f else ""
            if any(o.lower() in issuer_txt.lower() for o in offline):
                row(d, "letter", "Source unavailable", {"issuer": issuer_txt, "note": "no online channel; verification letter to be drafted"})
                c.add("source", "Source unavailable", "low", 0.9, f"The issuer of the {label} ('{issuer_txt}') has no online verification channel (simulated source).",
                      "SRC-ISSUER-01", [c.ev(d, issuer_f)], "Clears when the issuing office confirms the certificate by letter or an online record becomes available.", [d])
                continue
            rec = next((r for r in registry if r["doc_type"] == d.doc_type and num_f and _sq(r["number"]) == _sq(num_f.value)), None)
            if not rec:
                row(d, chans[0], "Verification pending", {"note": "no matching record"})
                continue
            key = "valid_till" if "valid_till" in rec else "issue_date"
            pf = c.fact(d, key)
            if pf and rec[key] != pf.normalised_value:
                row(d, rec["channel"], "Mismatch detected", {"registry": rec, "printed": pf.value})
                c.add("source", "Mismatch detected", "high", 0.93, f"Issuer record (simulated) shows {key.replace('_', ' ')} {_dmy(rec[key])}, printed {pf.value}.", "SRC-ISSUER-02",
                      [c.ev(d, pf)], "Clears if the printed certificate matches the issuer's record.", [d])
            else:
                row(d, rec["channel"], "Verified", {"registry": {k: rec[k] for k in ("number", "issuer", key)}})


# ---------------------------------------------------------------------------------------------
def risk(findings: list[Finding], rules: dict) -> tuple[str, float]:
    r = rules["risk"]
    open_f = [f for f in findings if f.status != "Verified"]
    score = sum(r["weights"][f.severity] for f in open_f)
    highs = sum(f.severity == "high" for f in open_f)
    if highs >= 2 or score >= r["red_at"]:
        return "Red", float(score)
    if highs >= 1 or score >= r["amber_at"]:  # asymmetric floor: one strong finding can never stay Green
        return "Amber", float(score)
    return "Green", float(score)


def run_checks(s: Session, app: Application) -> list[Finding]:
    for old in s.exec(select(Finding).where(Finding.application_id == app.id)).all():
        s.delete(old)
    for d in s.exec(select(Document).where(Document.application_id == app.id)).all():
        for sc in s.exec(select(SourceCheck).where(SourceCheck.document_id == d.id)).all():
            s.delete(sc)
    s.flush()
    c = Ctx(s, app)
    for fn in (check_completeness, check_expiry, check_contradictions, check_shared_land, check_timeline, check_twins, check_forensics, check_faculty, check_sources):
        fn(c)
    c.findings.sort(key=lambda f: (SEV_ORDER[f.severity], f.check_type))
    for f in c.findings:
        s.add(f)
    app.risk_lane, app.risk_score = risk(c.findings, c.rules)
    app.status, app.pipeline_stage = "Ready for review", "checked"
    s.add(app)
    s.commit()
    return c.findings
