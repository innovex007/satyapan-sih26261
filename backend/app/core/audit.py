"""Append-only audit log. Each event hashes its own content plus the previous event's hash (SHA-256 chain)."""
import hashlib
import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..models import AuditEvent


def _digest(ev: AuditEvent, prev: str) -> str:
    ts = ev.ts.replace(tzinfo=None).isoformat() if ev.ts.tzinfo else ev.ts.isoformat()
    raw = "|".join([prev, ts, ev.actor, ev.role, ev.action, ev.entity, ev.payload_json])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def log(s: Session, actor: str, role: str, action: str, entity: str, payload: dict | None = None) -> AuditEvent:
    last = s.exec(select(AuditEvent).order_by(AuditEvent.id.desc())).first()
    prev = last.hash if last else ""
    ev = AuditEvent(ts=datetime.now(timezone.utc).replace(microsecond=0), actor=actor, role=role, action=action, entity=entity,
                    payload_json=json.dumps(payload or {}, sort_keys=True, default=str), prev_hash=prev)
    ev.hash = _digest(ev, prev)
    s.add(ev)
    s.commit()
    return ev


def verify(s: Session) -> dict:
    prev, n = "", 0
    for ev in s.exec(select(AuditEvent).order_by(AuditEvent.id)).all():
        n += 1
        if ev.prev_hash != prev or ev.hash != _digest(ev, prev):
            return {"ok": False, "events": n, "broken_at": ev.id}
        prev = ev.hash
    return {"ok": True, "events": n, "broken_at": None}
