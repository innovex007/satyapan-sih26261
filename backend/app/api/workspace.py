import json
from pathlib import Path
from typing import Optional

import imagehash
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core import audit
from ..core.config import STORAGE_DIR
from ..core.db import engine, get_session
from ..models import Application, AuditEvent, Document, Fact, Finding, ImageFingerprint, Institution, SourceCheck
from ..rules.loader import load_rules

router = APIRouter(tags=["workspace"])
ROOT = Path(__file__).resolve().parents[3]
STATUS_PRIORITY = ["Mismatch detected", "Expired", "Manual review required", "Source unavailable", "Verification pending"]
GROUP_ORDER = ["Land & Building", "Safety & NOCs", "Academic & Faculty", "Finance", "Photos & Videos"]


def _finding(f: Finding) -> dict:
    return f.model_dump()


@router.get("/applications/{app_id}/workspace")
def workspace(app_id: str, s: Session = Depends(get_session)):
    app = s.get(Application, app_id)
    if not app:
        raise HTTPException(404, "application not found")
    inst = s.get(Institution, app.institution_id)
    rules = load_rules()
    docs = s.exec(select(Document).where(Document.application_id == app_id).order_by(Document.id)).all()
    findings = s.exec(select(Finding).where(Finding.application_id == app_id)).all()
    findings.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f.severity], f.id))
    srcs = s.exec(select(SourceCheck).where(SourceCheck.document_id.in_([d.id for d in docs]))).all() if docs else []

    def doc_status(d: Document) -> str:
        sts = [f.status for f in findings if d.id in (f.document_ids or []) and f.officer_action != "dismissed"]
        for st in STATUS_PRIORITY:
            if st in sts:
                return st
        return "Verified" if app.pipeline_stage == "checked" else "Verification pending"

    groups = {g: [] for g in GROUP_ORDER}
    for d in docs:
        groups.setdefault(d.category_group, []).append({
            "id": d.id, "filename": d.filename, "doc_type": d.doc_type, "label": rules["doc_types"].get(d.doc_type, {}).get("label", d.doc_type),
            "pages": d.pages, "kind": d.kind, "status": doc_status(d), "flags": sum(d.id in (f.document_ids or []) for f in findings)})
    own = {d.id for d in docs}
    ext_ids = {e["document_id"] for f in findings for e in (f.evidence or []) if e.get("document_id") and e["document_id"] not in own}
    external = [{"id": d.id, "filename": d.filename, "doc_type": d.doc_type, "label": rules["doc_types"].get(d.doc_type, {}).get("label", d.doc_type),
                 "pages": d.pages, "kind": d.kind, "status": "Verified", "flags": 0}
                for d in (s.exec(select(Document).where(Document.id.in_(ext_ids))).all() if ext_ids else [])]
    present = {d.doc_type for d in docs}
    missing = [{"doc_type": t, "label": rules["doc_types"][t]["label"]} for t in rules["categories"][app.category]["required"] if t not in present]
    return {
        "application": app, "institution": inst, "groups": [{"group": g, "documents": v} for g, v in groups.items() if v], "missing": missing,
        "findings": [_finding(f) for f in findings], "external": external,
        "source_checks": [{"document_id": x.document_id, "channel": x.channel, "result": x.result, "simulated": x.simulated, "response": x.response} for x in srcs],
        "is_archive": app.cycle_label != "Current cycle",
    }


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: int, s: Session = Depends(get_session)):
    d = s.get(Document, doc_id)
    if not d:
        raise HTTPException(404)
    p = STORAGE_DIR / d.file_path
    return FileResponse(p, media_type="application/pdf" if p.suffix.lower() == ".pdf" else "image/jpeg", filename=d.filename, content_disposition_type="inline")


@router.get("/documents/{doc_id}/facts")
def document_facts(doc_id: int, s: Session = Depends(get_session)):
    return s.exec(select(Fact).where(Fact.document_id == doc_id)).all()


class ActionIn(BaseModel):
    action: str  # accept | dismiss | clarify
    note: str = ""
    role: str = "Scrutiny officer"


@router.post("/findings/{finding_id}/action")
def finding_action(finding_id: int, body: ActionIn, s: Session = Depends(get_session)):
    f = s.get(Finding, finding_id)
    if not f:
        raise HTTPException(404)
    mapping = {"accept": "accepted", "dismiss": "dismissed", "clarify": "clarification_requested"}
    if body.action not in mapping:
        raise HTTPException(400, "action must be accept, dismiss or clarify")
    if body.action in ("dismiss", "clarify") and not body.note.strip():
        raise HTTPException(400, "a reason is required")
    f.officer_action, f.officer_note = mapping[body.action], body.note.strip()
    s.add(f)
    s.commit()
    audit.log(s, "officer", body.role, f"finding.{mapping[body.action]}", f"finding:{f.id}",
              {"application": f.application_id, "rule": f.rule_id, "status": f.status, "note": f.officer_note})
    return f


# ---- twin search ----------------------------------------------------------------------------
def _img_info(s: Session, d: Document) -> dict:
    a = s.get(Application, d.application_id)
    i = s.get(Institution, a.institution_id)
    return {"document_id": d.id, "application_id": a.id, "filename": d.filename, "institution": i.name, "permanent_id": i.permanent_id,
            "cycle_label": a.cycle_label, "session": a.academic_session, "archive": a.cycle_label != "Current cycle"}


@router.get("/twins")
def twins(document_id: int, limit: int = 4, s: Session = Depends(get_session)):
    """Nearest images from OTHER institutions: copies first (pHash), then ORB-verified re-shots, then the closest non-matches."""
    from ..pipeline import similarity as simg

    d = s.get(Document, document_id)
    fp = s.exec(select(ImageFingerprint).where(ImageFingerprint.document_id == document_id)).first()
    if not d or not fp:
        raise HTTPException(404, "no fingerprint for this document")
    tc = load_rules()["twin"]
    rows = s.exec(select(ImageFingerprint, Document).join(Document, Document.id == ImageFingerprint.document_id)
                  .where(ImageFingerprint.institution_id != fp.institution_id)).all()
    scored = []
    for ofp, od in rows:
        r = simg.compare(fp.phash, ofp.phash, STORAGE_DIR / d.file_path, STORAGE_DIR / od.file_path, tc, simg.orb_applies(d.doc_type, od.doc_type))
        inl = r["orb"]["inliers"] if r["orb"] else None
        rank = (0, r["phash_distance"]) if r["kind"] == "copy" else (1, -inl) if r["kind"] == "reshot" else (2, -(inl or 0)) if inl is not None else (3, r["phash_distance"])
        scored.append((rank, od, r, inl))
    scored.sort(key=lambda x: x[0])
    out = []
    for _, od, r, inl in scored[:limit]:
        dist = r["phash_distance"]
        out.append({**_img_info(s, od), "phash_distance": dist, "inliers": inl, "similarity_pct": round(100 * (1 - dist / 64)),
                    "kind": r["kind"], "twin": r["twin"], "different_institution": True, "has_lines": inl is not None and inl > 0})
    return {"query": _img_info(s, d), "thresholds": {"phash_copy": tc["hash_flag_max"], "phash_candidate": tc["hash_candidate_max"],
                                                     "orb_min_inliers": tc["orb"]["min_inliers"]}, "matches": out}


@router.get("/twins/match.png")
def twin_match_image(a: int, b: int, s: Session = Depends(get_session)):
    """Both images side by side with the RANSAC-verified keypoint matches drawn as lines."""
    from fastapi.responses import Response

    from ..pipeline import similarity as simg

    da, db = s.get(Document, a), s.get(Document, b)
    if not da or not db:
        raise HTTPException(404)
    return Response(simg.draw_matches(STORAGE_DIR / da.file_path, STORAGE_DIR / db.file_path), media_type="image/png")


@router.get("/twins/sources")
def twin_sources(s: Session = Depends(get_session)):
    """Image documents of the current cycle, those with twin findings first."""
    flagged = {did: f for f in s.exec(select(Finding).where(Finding.check_type == "twin")).all() for did in (f.document_ids or [])[:1]}
    rows = s.exec(select(Document, Application).join(Application, Application.id == Document.application_id)
                  .where(Document.kind == "image", Application.academic_session == "2026-27")).all()
    def kind(did):  # copy (pHash) | reshot (keypoints) | None, as recorded on the twin finding
        f = flagged.get(did)
        return next((e.get("twin_kind") for e in (f.evidence or []) if e.get("twin_kind")), None) if f else None

    out = [{**_img_info(s, d), "flagged": d.id in flagged, "twin_kind": kind(d.id), "label": f"{a.id} · {d.filename}"} for d, a in rows]
    # flagged first; the hero cases (EoA-DEMO-*) lead, and 0417's re-shot lab photo is the default
    out.sort(key=lambda r: (not r["flagged"], "DEMO" not in r["application_id"], r["application_id"], r["filename"]))
    return out


# ---- audit / eval / process -------------------------------------------------------------------
@router.get("/audit")
def audit_list(limit: int = 200, s: Session = Depends(get_session)):
    return s.exec(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()


@router.post("/audit/verify")
def audit_verify(s: Session = Depends(get_session)):
    return audit.verify(s)


@router.get("/eval/results")
def eval_results():
    p = ROOT / "eval" / "results.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _process(app_id: str):
    from ..pipeline.checks.rules import run_checks
    from ..pipeline.run import extract_application

    with Session(engine) as s:
        a = s.get(Application, app_id)
        extract_application(s, a)
        run_checks(s, a)
        audit.log(s, "pipeline", "system", "application.reprocessed", app_id, {})


@router.post("/applications/{app_id}/process")
def process(app_id: str, bg: BackgroundTasks, s: Session = Depends(get_session)):
    if not s.get(Application, app_id):
        raise HTTPException(404)
    bg.add_task(_process, app_id)
    return {"queued": app_id}
