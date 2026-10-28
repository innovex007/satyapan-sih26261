"""Read-only endpoints behind the Forensics lab, Source checks, Rule files and Audit log pages. No new logic: everything shown here
was produced by the pipeline (documents, facts, findings, source checks, audit events) or is the rule file itself."""
import io
import re
from datetime import datetime
from pathlib import Path

import pikepdf
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..core.config import STORAGE_DIR
from ..core.db import get_session
from ..models import Application, AuditEvent, Document, Fact, Finding, Institution, SourceCheck
from ..pipeline.sources import simulated as sim
from ..rules.loader import DEFAULT, load_rules

router = APIRouter(tags=["pages"])
CHANNELS = {"qr": "QR code", "signature": "Digital signature", "issuer_portal": "Issuer portal (simulated)",
            "digilocker": "DigiLocker (simulated)", "letter": "Letter"}


# ---- Forensics lab ------------------------------------------------------------------------------
@router.get("/forensics/documents")
def forensic_documents(s: Session = Depends(get_session)):
    flagged = {did for f in s.exec(select(Finding).where(Finding.check_type == "forensic")).all() for did in (f.document_ids or [])}
    rows = s.exec(select(Document, Application).join(Application, Application.id == Document.application_id)
                  .where(Document.doc_type == "affidavit", Application.academic_session == "2026-27")).all()
    out = [{"document_id": d.id, "application_id": a.id, "filename": d.filename, "flagged": d.id in flagged,
            "label": f"{a.id} · {d.filename}"} for d, a in rows]
    out.sort(key=lambda r: (not r["flagged"], "DEMO" not in r["application_id"], r["application_id"]))  # flagged first, hero cases before the rest
    return out


def _pdf_date(v) -> str | None:
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", str(v or ""))
    return f"{m[1]}-{m[2]}-{m[3]} {m[4] or '00'}:{m[5] or '00'}" if m else None


@router.get("/forensics/{doc_id}")
def forensic_detail(doc_id: int, s: Session = Depends(get_session)):
    from ..pipeline.checks.rules import _fonts_at

    d = s.get(Document, doc_id)
    if not d or d.kind != "text":
        raise HTTPException(404, "no forensic data for this document")
    path = STORAGE_DIR / d.file_path
    raw = path.read_bytes()
    info = sim.signature_state(path)
    with pikepdf.open(io.BytesIO(raw)) as pk:
        meta = {k.lstrip("/"): str(v) for k, v in pk.docinfo.items()}
    metadata = [{"field": "Producer", "value": meta.get("Producer")}, {"field": "Creator", "value": meta.get("Creator")},
                {"field": "Created", "value": _pdf_date(meta.get("CreationDate"))}, {"field": "Modified", "value": _pdf_date(meta.get("ModDate"))},
                {"field": "Title", "value": meta.get("Title")}, {"field": "File size", "value": f"{len(raw):,} bytes"}]
    ends = [m.end() for m in re.finditer(rb"%%EOF", raw)]
    signed_at = next((i for i, off in enumerate(ends) if b"/ByteRange" in raw[:off]), None)  # signing is itself an incremental write
    modified = info["state"] == "modified_after_signing"
    timeline = []
    if signed_at is None:
        timeline = [{"revision": i + 1, "label": "Saved (no digital signature)" if i == 0 else "Incremental update", "bytes": off, "after_signing": False} for i, off in enumerate(ends)]
    else:
        timeline.append({"revision": 1, "label": "Saved and digitally signed", "bytes": ends[signed_at], "after_signing": False})
        for n, off in enumerate(ends[signed_at + 1:], start=2):
            timeline.append({"revision": n, "label": "Edited after signing: page content replaced" if modified else "Incremental update after signing", "bytes": off, "after_signing": True})
    facts = {f.key: f for f in s.exec(select(Fact).where(Fact.document_id == d.id)).all()}
    indicators = []
    if info["state"] == "modified_after_signing":
        indicators.append(f"Incremental save after signing ({len(timeline) - 1} later save{'s' if len(timeline) > 2 else ''}; the signature covers only revision 1)")
    if info["producer"] and re.search(r"editor", info["producer"], re.I):
        indicators.append(f"Editing software named in the metadata: {info['producer']}")
    df = facts.get("affidavit_date")
    refs = [facts[k] for k in ("institution_name", "signatory") if k in facts]
    if df and refs:
        ref = set().union(*[_fonts_at(path, r.bbox) for r in refs])
        mine = _fonts_at(path, df.bbox)
        if ref and mine and not (mine & ref):
            indicators.append("Font outlier in the date field: " + ", ".join(f"{n} {sz}pt" for n, sz in sorted(mine)) + " amid " + ", ".join(f"{n} {sz}pt" for n, sz in sorted(ref)))
    n = len(indicators)
    summary = (f"{n} independent indicator{'s' if n != 1 else ''} → Manual review required (preliminary)"
               if info["state"] == "modified_after_signing" else "No forensic indicators found")
    a = s.get(Application, d.application_id)
    return {"document_id": d.id, "application_id": a.id, "filename": d.filename, "metadata": metadata, "signature": info["state"],
            "timeline": timeline, "indicators": indicators, "summary": summary, "flagged": info["state"] == "modified_after_signing",
            "ela": None}


# ---- Source checks --------------------------------------------------------------------------------
def _letter(s: Session, d: Document, a: Application, inst: Institution) -> str:
    f = {x.key: x.value for x in s.exec(select(Fact).where(Fact.document_id == d.id)).all()}
    label = load_rules()["doc_types"].get(d.doc_type, {}).get("label", d.doc_type)
    return (f"To,\nThe Issuing Officer,\n{f.get('issuer', 'Issuing office')}\n\n"
            f"Subject: Request to verify {label} No. {f.get('certificate_no') or f.get('noc_number') or '(number)'}\n"
            f"Reference: Application {a.id} · {inst.name} (#{inst.permanent_id})\n\n"
            f"Sir / Madam,\n\nAn application for approval has been received from {f.get('institution_name', inst.name)}. "
            f"The applicant has furnished a {label} (No. {f.get('certificate_no') or f.get('noc_number') or '(number)'}, "
            f"dated {f.get('issue_date', '(date)')}) for survey {f.get('survey_no', '(survey no.)')}, {f.get('village', '')}. "
            f"As your office has no online verification channel, kindly confirm by reply whether this certificate was issued by you and remains in force.\n\n"
            f"Yours faithfully,\nScrutiny Officer\n(Prototype letter · synthetic data · not an official communication)")


@router.get("/sources")
def source_checks(s: Session = Depends(get_session)):
    rows = s.exec(select(SourceCheck, Document, Application, Institution).join(Document, Document.id == SourceCheck.document_id)
                  .join(Application, Application.id == Document.application_id).join(Institution, Institution.id == Application.institution_id)
                  .where(Application.academic_session == "2026-27").order_by(SourceCheck.id)).all()
    labels = load_rules()["doc_types"]
    out = []
    for sc, d, a, inst in rows:
        number = next((x.value for x in s.exec(select(Fact).where(Fact.document_id == d.id, Fact.key.in_(["noc_number", "certificate_no"]))).all()), None)
        out.append({"id": sc.id, "application_id": a.id, "institution": inst.name, "document_id": d.id, "filename": d.filename,
                    "document": labels.get(d.doc_type, {}).get("label", d.doc_type), "channel": sc.channel, "channel_label": CHANNELS.get(sc.channel, sc.channel),
                    "result": sc.result, "requested_at": sc.requested_at, "simulated": sc.simulated,
                    "request": {"channel": CHANNELS.get(sc.channel, sc.channel), "application": a.id, "document": d.filename, "document_number": number,
                                "requested_at": sc.requested_at.isoformat() if sc.requested_at else None},
                    "response": sc.response, "letter": _letter(s, d, a, inst) if sc.result == "Source unavailable" else None})
    return out


# ---- Rule files -----------------------------------------------------------------------------------
@router.get("/rules/active")
def active_rules():
    r = load_rules()
    t, tol, tw = r["tolerances"], r["tolerances"], r["twin"]
    start = r["session"]["start"]
    rows = [
        ("CHK-COMPLETE-01", "Required documents for the application category are all present", "per-category checklist", "Verification pending"),
        ("CHK-EXPIRY-01", "Fire NOC / university NOC valid till is on or after the session start", f"session starts {start}", "Expired"),
        ("CHK-XDOC-LAND-01", "Land area agrees across deed, plan and land-use certificate (and last year's file)", f"±{tol['land_area_pct']}%", "Mismatch detected"),
        ("CHK-XDOC-SURVEY-01", "Survey number agrees across land documents", "exact", "Mismatch detected"),
        ("CHK-SHAREDLAND-01", "Same survey number + village not claimed by another institution", "exact match, later filer flagged", "Manual review required"),
        ("CHK-TIMELINE-01", "Fire NOC issue date is not before the building-plan approval date", "date order", "Mismatch detected"),
        ("CHK-TIMELINE-02", "No issue or signing date falls on a Sunday", "weekday ≠ Sunday", "Mismatch detected"),
        ("CHK-TWIN-01", "Photo is not a copy or a re-shot of another institution's photo", f"pHash ≤ {tw['hash_flag_max']}, or ≤ {tw['hash_candidate_max']} and ≥ {tw['orb']['min_inliers']} ORB inliers", "Manual review required"),
        ("CHK-FORENSIC-01", "No incremental save after a digital signature", f"≥ {r['forensics']['min_independent_signals']} indicator", "Manual review required"),
        ("CHK-FACULTY-01", "Faculty ID not listed by another institution in this cycle", "exact ID", "Manual review required"),
        ("SRC-QR-01", "QR code content agrees with the printed text", "exact", "Mismatch detected"),
        ("SRC-SIG-01", "Affidavit carries a digital signature that still verifies", "valid signature", "Manual review required"),
        ("SRC-ISSUER-01", "Issuer has an online verification channel (simulated)", "channel available", "Source unavailable"),
        ("SRC-ISSUER-02", "Printed validity / issue date agrees with the issuer's record (simulated)", "exact", "Mismatch detected"),
    ]
    p = Path(DEFAULT)
    return {"name": r["name"], "version": r["version"], "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes"),
            "file": p.name, "yaml_text": p.read_text(encoding="utf-8"),
            "rules": [{"id": a, "checks": b, "threshold": c, "status": d} for a, b, c, d in rows]}


# ---- Audit log (paged) -----------------------------------------------------------------------------
@router.get("/audit/page")
def audit_page(limit: int = 25, offset: int = 0, s: Session = Depends(get_session)):
    total = len(s.exec(select(AuditEvent.id)).all())
    events = s.exec(select(AuditEvent).order_by(AuditEvent.id.desc()).offset(offset).limit(limit)).all()
    return {"total": total, "events": [{"id": e.id, "ts": e.ts, "actor": e.actor, "role": e.role, "action": e.action, "entity": e.entity,
                                         "hash": e.hash[:10], "prev_hash": e.prev_hash[:10]} for e in events]}
