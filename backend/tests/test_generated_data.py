"""Checks the seeded dataset against its own answer key: bboxes land on the right text, scans really are image-only,
signatures are in the state the key says. Requires `make seed` to have been run."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KEY = ROOT / "data" / "answer_key.json"
FILES = ROOT / "storage"

pytestmark = pytest.mark.skipif(not KEY.exists(), reason="run `make seed` first")


def _key():
    return json.loads(KEY.read_text(encoding="utf-8"))


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9./]", "", s.lower())


def _hits(spans, fact):
    """Spans whose centre lies inside the fact bbox (with slack) and whose text contains the fact value."""
    x0, y0, x1, y1 = fact["bbox"]
    pad_x, pad_y = 0.02, 0.012
    want = _squash(fact["value"])
    for s in spans:
        if s.page != fact["page"]:
            continue
        cx, cy = (s.bbox[0] + s.bbox[2]) / 2, (s.bbox[1] + s.bbox[3]) / 2
        if x0 - pad_x <= cx <= x1 + pad_x and y0 - pad_y <= cy <= y1 + pad_y and (want in _squash(s.text) or _squash(s.text) in want):
            return True
    return False


def _docs(kind):
    for a in _key()["applications"]:
        for d in a["documents"]:
            if d["kind"] == kind and d["facts"]:
                yield a["id"], d


def test_counts():
    k = _key()
    assert len(k["applications"]) == 30
    assert len(k["defects"]) >= 40
    assert {d["type_id"] for d in k["defects"]} == set(range(1, 11))
    assert sum(a["clean"] for a in k["applications"]) >= 8
    for h in ("EoA-DEMO-0417", "EoA-DEMO-0422", "EoA-DEMO-0431", "EoA-DEMO-0440"):
        assert any(a["id"] == h for a in k["applications"])


def test_every_defect_is_fully_described():
    for d in _key()["defects"]:
        for f in ("id", "type", "application_id", "doc_type", "expected_status"):
            assert f in d
        assert d["expected_status"] in ("Verified", "Mismatch detected", "Expired", "Verification pending", "Source unavailable", "Manual review required")


def test_text_layer_bboxes_match_answer_key():
    from app.pipeline.ocr import read_document

    total = ok = 0
    misses = []
    for app_id, d in _docs("text"):
        res = read_document(FILES / d["path"], engine="textlayer")
        for f in d["facts"]:
            total += 1
            if _hits(res.spans, f):
                ok += 1
            else:
                misses.append((app_id, d["file"], f["key"], f["value"]))
    assert total > 300
    assert ok / total > 0.98, misses[:10]


def test_scans_are_image_only_and_ocr_reads_them():
    import pdfplumber

    from app.pipeline.ocr import read_document

    scans = list(_docs("scan"))
    assert len(scans) >= 3
    total = ok = 0
    for app_id, d in scans:
        with pdfplumber.open(FILES / d["path"]) as pdf:
            assert not "".join((p.extract_text() or "") for p in pdf.pages).strip(), f"{d['file']} has a text layer"
        res = read_document(FILES / d["path"])
        assert set(res.engines.values()) == {"rapidocr"}
        for f in d["facts"]:
            total += 1
            ok += _hits(res.spans, f)
    assert ok / total > 0.85, f"OCR matched {ok}/{total} facts on scans"


def test_signature_states():
    import io

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    seen = set()
    for a in _key()["applications"] + _key()["last_year_applications"]:
        for d in a["documents"]:
            if d["doc_type"] != "affidavit":
                continue
            reader = PdfFileReader(io.BytesIO((FILES / d["path"]).read_bytes()))
            sigs = reader.embedded_signatures
            if d["signature"] == "none":
                assert not sigs
            else:
                assert len(sigs) == 1
                st = validate_pdf_signature(sigs[0])
                if d["signature"] == "valid":
                    assert st.intact and st.modification_level.value == 0, d["file"]
                elif d["signature"] == "broken":
                    assert not st.intact
                elif d["signature"] == "modified_after_signing":
                    assert st.intact and st.modification_level.value > 0
            seen.add(d["signature"])
    assert seen == {"valid", "none", "broken", "modified_after_signing"}
