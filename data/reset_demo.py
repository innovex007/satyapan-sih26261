"""Restore a clean demo state without re-seeding: every finding back to 'no officer action', and the audit log cut back to the
pipeline's own events (officer actions / resets recorded after the last pipeline run are removed; the hash chain stays valid
because only the tail is dropped).   python data/reset_demo.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.core import audit  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.models import AuditEvent, Finding  # noqa: E402

with Session(engine) as s:
    touched = s.exec(select(Finding).where((Finding.officer_action != "none") | (Finding.officer_note != ""))).all()
    for f in touched:
        f.officer_action, f.officer_note = "none", ""
        s.add(f)
    pipeline_ids = [e.id for e in s.exec(select(AuditEvent).where(AuditEvent.action == "application.processed")).all()]
    cutoff = max(pipeline_ids) if pipeline_ids else 0
    tail = s.exec(select(AuditEvent).where(AuditEvent.id > cutoff)).all()
    for e in tail:
        s.delete(e)
    s.commit()
    total = len(s.exec(select(Finding)).all())
    open_flags = len(s.exec(select(Finding).where(Finding.officer_action == "none")).all())
    v = audit.verify(s)
print(f"Findings reset: {len(touched)}   audit events removed: {len(tail)}")
print(f"Open flags: {open_flags}/{total}   audit chain: {'intact' if v['ok'] else 'BROKEN at ' + str(v['broken_at'])} ({v['events']} events)")
sys.exit(0 if v["ok"] and open_flags == total else 1)
