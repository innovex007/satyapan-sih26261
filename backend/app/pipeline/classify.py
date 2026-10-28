"""Document type from filename hints + keywords in the (OCR'd) text. No ML."""
import re

from ..rules.loader import load_rules


def _sq(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def classify(filename: str, text: str, is_image: bool) -> tuple[str, float]:
    rules = load_rules()
    fn = _sq(filename.rsplit(".", 1)[0])
    if is_image:  # photos: filename only (layout heuristics are roadmap)
        for t in ("lab_video_frame", "building_photo", "lab_photo"):
            if any(h in fn for h in rules["filename_hints"][t]):
                return t, 0.9
        return "lab_photo", 0.4
    head, body = _sq(text[:300]), _sq(text)
    scores = {}
    for t, meta in rules["doc_types"].items():
        sc = 0.0
        for kw in meta["keywords"]:
            k = _sq(kw)
            if k and k in head:
                sc += 3
            if k and k in body:
                sc += 1
        for h in rules["filename_hints"].get(t, []):
            if h in fn:
                sc += 2
                break
        scores[t] = sc
    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    return (best, round(scores[best] / total, 2)) if scores[best] > 0 else ("unclassified", 0.0)
