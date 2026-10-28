"""Classification and fact-extraction accuracy against data/answer_key.json. Text-layer and scanned documents are reported separately."""
import json
import re
from pathlib import Path

from sqlmodel import Session, select

from ..models import Document, Fact

KEY = Path(__file__).resolve().parents[3] / "data" / "answer_key.json"


def _sq(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _key_docs():
    k = json.loads(KEY.read_text(encoding="utf-8"))
    for a in k["applications"] + k["last_year_applications"]:
        for d in a["documents"]:
            yield a["id"], d


def classification_accuracy(s: Session) -> dict:
    got = {(d.application_id, d.filename): d.doc_type for d in s.exec(select(Document)).all()}
    total = correct = 0
    misses = []
    for app_id, d in _key_docs():
        total += 1
        if got.get((app_id, d["file"])) == d["doc_type"]:
            correct += 1
        else:
            misses.append((app_id, d["file"], d["doc_type"], got.get((app_id, d["file"]))))
    return {"total": total, "correct": correct, "accuracy": correct / total, "misses": misses}


def fact_accuracy(s: Session) -> dict:
    docs = {(d.application_id, d.filename): d for d in s.exec(select(Document)).all()}
    facts: dict[int, list[Fact]] = {}
    for f in s.exec(select(Fact)).all():
        facts.setdefault(f.document_id, []).append(f)
    out = {k: {"expected": 0, "predicted": 0, "tp": 0} for k in ("text", "scan")}
    for app_id, d in _key_docs():
        if d["kind"] not in out or not d["facts"]:
            continue
        m = out[d["kind"]]
        pred = [(f.key, _sq(f.normalised_value)) for f in facts.get(docs[(app_id, d["file"])].id, [])] if (app_id, d["file"]) in docs else []
        exp = [(f["key"], _sq(f["normalised"])) for f in d["facts"]]
        m["expected"] += len(exp)
        m["predicted"] += len(pred)
        pool = list(pred)
        for e in exp:
            if e in pool:
                pool.remove(e)
                m["tp"] += 1
    for m in out.values():
        m["precision"] = m["tp"] / m["predicted"] if m["predicted"] else 0.0
        m["recall"] = m["tp"] / m["expected"] if m["expected"] else 0.0
        m["f1"] = 2 * m["precision"] * m["recall"] / (m["precision"] + m["recall"]) if m["tp"] else 0.0
    return out
