"""Key facts per document type from OCR spans: find the label, take the value to its right on the same row."""
import re
from datetime import datetime
from difflib import SequenceMatcher

from ..rules.loader import load_rules
from .ocr import Span


def _sq(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _norm(kind: str, raw: str) -> str:
    if kind == "date":
        m = re.search(r"(\d{2})\D?(\d{2})\D?(\d{4})", raw)
        if m:
            try:
                return datetime(int(m[3]), int(m[2]), int(m[1])).date().isoformat()
            except ValueError:
                pass
        return raw.strip()
    if kind == "area":
        m = re.search(r"\d+(?:[.,]\d+)?", raw)
        return f"{float(m[0].replace(',', '.')):.2f}" if m else raw.strip()
    if kind == "int":
        return re.sub(r"\D", "", raw) or raw.strip()
    return re.sub(r"\s+", " ", raw.strip().lower())


def _is_label(span: Span, label: str) -> bool:
    if span.bbox[0] > 0.3 or len(span.text) > len(label) + 6:
        return False
    a, b = _sq(span.text), _sq(label)
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.86


def extract_facts(doc_type: str, spans: list[Span]) -> list[dict]:
    tpl = load_rules()["extraction"].get(doc_type, [])
    out = []
    for label, key, kind in tpl:
        for lab in spans:
            if lab.page != 1 or not _is_label(lab, label):
                continue
            cy = (lab.bbox[1] + lab.bbox[3]) / 2
            cands = [s for s in spans if s is not lab and s.page == lab.page and s.bbox[0] >= lab.bbox[2] - 0.01
                     and abs((s.bbox[1] + s.bbox[3]) / 2 - cy) <= 0.016]
            if cands:
                v = min(cands, key=lambda s: s.bbox[0])
                out.append({"key": key, "value": v.text, "normalised": _norm(kind, v.text), "page": v.page, "bbox": v.bbox,
                            "confidence": round(v.conf, 3)})
                break
    if doc_type == "faculty_list":
        for s in spans:
            m = re.search(r"FAC-?\s?\d{6}", s.text)
            if m:
                fid = m[0].replace(" ", "")
                out.append({"key": "faculty_id", "value": fid, "normalised": fid.lower(), "page": s.page, "bbox": s.bbox,
                            "confidence": round(s.conf, 3)})
    return out
