from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from ..core.db import get_session
from ..models import Application, Document, Finding, Institution

router = APIRouter(tags=["applications"])
CURRENT_SESSION = "2026-27"
LANE_ORDER = {"Red": 0, "Amber": 1, "Green": 2}


def _rows(s: Session, session: str):
    docs = dict(s.exec(select(Document.application_id, func.count()).group_by(Document.application_id)).all())
    flags = dict(s.exec(select(Finding.application_id, func.count()).where(Finding.officer_action == "none").group_by(Finding.application_id)).all())
    q = select(Application, Institution).join(Institution, Institution.id == Application.institution_id).where(Application.academic_session == session)
    for app, inst in s.exec(q).all():
        yield {
            "id": app.id, "institution": inst.name, "permanent_id": inst.permanent_id, "category": app.category,
            "region": inst.region, "state": inst.state, "submitted_at": app.submitted_at, "documents": docs.get(app.id, 0),
            "open_flags": flags.get(app.id, 0), "risk_lane": app.risk_lane, "status": app.status,
        }


@router.get("/applications")
def list_applications(q: Optional[str] = None, risk_lane: Optional[str] = None, category: Optional[str] = None,
                      region: Optional[str] = None, session: str = CURRENT_SESSION, s: Session = Depends(get_session)):
    rows = list(_rows(s, session))
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["id"].lower() or needle in r["institution"].lower()]
    if risk_lane:
        rows = [r for r in rows if (r["risk_lane"] or "Not processed") == risk_lane]
    if category:
        rows = [r for r in rows if r["category"] == category]
    if region:
        rows = [r for r in rows if r["region"] == region]
    # highest risk first; unprocessed applications keep submission order
    rows.sort(key=lambda r: (LANE_ORDER.get(r["risk_lane"], 3), r["submitted_at"]))
    return rows


@router.get("/applications/meta")
def meta(session: str = CURRENT_SESSION, s: Session = Depends(get_session)):
    rows = list(_rows(s, session))
    return {"categories": sorted({r["category"] for r in rows}), "regions": sorted({r["region"] for r in rows}),
            "risk_lanes": ["Red", "Amber", "Green", "Not processed"]}
