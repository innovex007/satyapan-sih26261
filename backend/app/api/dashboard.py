import json

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..core.config import STORAGE_DIR
from ..core.db import get_session
from ..models import Application, Finding, SourceCheck

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
def summary(s: Session = Depends(get_session)):
    apps = s.exec(select(Application).where(Application.academic_session == "2026-27")).all()
    lanes = {"Green": 0, "Amber": 0, "Red": 0, "Not processed": 0}
    for a in apps:
        lanes[a.risk_lane if a.risk_lane in lanes else "Not processed"] += 1
    ids = {a.id for a in apps}
    findings = [f for f in s.exec(select(Finding)).all() if f.application_id in ids]
    by_type: dict[str, int] = {}
    for f in findings:
        by_type[f.check_type] = by_type.get(f.check_type, 0) + 1
    attention = []
    for a in sorted([a for a in apps if a.risk_lane in ("Red", "Amber")], key=lambda a: (a.risk_lane != "Red", -a.risk_score))[:5]:
        top = next((f for f in findings if f.application_id == a.id and f.severity == "high"), None)
        attention.append({"id": a.id, "lane": a.risk_lane, "reason": top.reason if top else "Flags awaiting review"})
    timing = STORAGE_DIR / "pipeline_timing.json"
    avg = json.loads(timing.read_text())["avg_seconds_per_application"] if timing.exists() else None
    pending = s.exec(select(SourceCheck).where(SourceCheck.result == "Verification pending")).all()
    return {
        "received": len(apps), "ready_for_review": sum(a.status == "Ready for review" for a in apps),
        "open_flags": sum(f.officer_action == "none" for f in findings), "avg_seconds_per_application": avg,
        "risk_lanes": lanes, "findings_by_type": by_type, "needs_attention": attention,
        "source_checks_pending": {"count": len(pending), "oldest_age_hours": None}, "processed": sum(a.risk_lane is not None for a in apps),
    }
