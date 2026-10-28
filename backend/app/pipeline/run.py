"""Pipeline: intake -> classify -> OCR/extract (Evidence Graph facts) -> fingerprints -> checks -> risk lane.
CLI:  python -m app.pipeline.run --all        (also called at the end of `make seed`)"""
import json
import sys
import time
from pathlib import Path

from PIL import Image
from sqlmodel import Session, select

from ..core import audit
from ..core.config import STORAGE_DIR
from ..core.db import engine
from ..models import Application, Document, Fact, ImageFingerprint, Institution
from ..rules.loader import load_rules
from . import similarity
from .checks.rules import run_checks
from .classify import classify
from .extract import extract_facts
from .ocr import read_document

TIMING = STORAGE_DIR / "pipeline_timing.json"


def extract_application(s: Session, app: Application) -> None:
    rules = load_rules()
    for d in s.exec(select(Document).where(Document.application_id == app.id)).all():
        for f in s.exec(select(Fact).where(Fact.document_id == d.id)).all():
            s.delete(f)
        for fp in s.exec(select(ImageFingerprint).where(ImageFingerprint.document_id == d.id)).all():
            s.delete(fp)
        path = STORAGE_DIR / d.file_path
        is_image = path.suffix.lower() != ".pdf"
        res = read_document(path)
        text = "\n".join(sp.text for sp in res.spans)
        d.doc_type, d.classify_confidence = classify(d.filename, text, is_image)
        d.category_group = rules["doc_types"].get(d.doc_type, {}).get("group", "Unclassified")
        d.pages = res.pages or 1
        engines = set(res.engines.values())
        d.kind = "image" if is_image else ("text" if engines == {"textlayer"} else "scan")
        d.ocr_engine = ",".join(sorted(engines)) if engines else "none"
        if is_image:
            fp = similarity.fingerprint(Image.open(path))
            inst_id = app.institution_id
            s.add(ImageFingerprint(document_id=d.id, institution_id=inst_id, phash=fp["phash"], dhash=fp["dhash"], whash=fp["whash"]))
        for f in extract_facts(d.doc_type, res.spans):
            s.add(Fact(document_id=d.id, key=f["key"], value=f["value"], normalised_value=f["normalised"], page=f["page"], bbox=f["bbox"],
                       confidence=f["confidence"]))
        s.add(d)
    app.pipeline_stage = "extracted"
    s.add(app)
    s.commit()


def run_all(current_only_checks: bool = True, report: bool = True) -> dict:
    t_all = time.time()
    timing: dict[str, float] = {}
    with Session(engine) as s:
        apps = s.exec(select(Application)).all()
        for a in apps:  # previous-cycle and archive files are extracted too (cross-year checks and twin evidence)
            t0 = time.time()
            extract_application(s, a)
            timing[a.id] = time.time() - t0
        current = [a for a in apps if a.academic_session == "2026-27"]
        current_ids = [a.id for a in current]
        for a in current:
            t0 = time.time()
            n = len(run_checks(s, a))
            timing[a.id] += time.time() - t0
            audit.log(s, "pipeline", "system", "application.processed", a.id, {"findings": n, "risk_lane": a.risk_lane})
        s.commit()
    per_app = [timing[i] for i in current_ids]
    out = {"applications": len(current_ids), "avg_seconds_per_application": round(sum(per_app) / len(per_app), 2),
           "total_seconds": round(time.time() - t_all, 1)}
    TIMING.write_text(json.dumps({**out, "per_application": {i: round(timing[i], 2) for i in current_ids}}, indent=1), encoding="utf-8")
    if report:
        from .accuracy import classification_accuracy, fact_accuracy

        with Session(engine) as s:
            out["classification"] = classification_accuracy(s)
            out["facts"] = fact_accuracy(s)
        c, f = out["classification"], out["facts"]
        print(f"Processed {out['applications']} applications in {out['total_seconds']}s (avg {out['avg_seconds_per_application']}s each)")
        print(f"Classification accuracy: {c['correct']}/{c['total']} ({c['accuracy']:.1%})  misses: {c['misses'][:5]}")
        for kind in ("text", "scan"):
            m = f[kind]
            print(f"Fact extraction ({kind}-layer): matched {m['tp']}/{m['expected']}  precision {m['precision']:.3f}  recall {m['recall']:.3f}  F1 {m['f1']:.3f}")
    return out


if __name__ == "__main__":
    run_all()
    sys.exit(0)
