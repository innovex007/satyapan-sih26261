"""Reads a document into text spans with normalised top-left bounding boxes.

Order of preference (OCR_ENGINE=auto): embedded text layer (pdfplumber) -> RapidOCR (onnxruntime, CPU) -> Tesseract (eng+hin).
A page only falls through to an OCR engine when its text layer is effectively empty, so scans are OCR'd and born-digital
PDFs are read exactly. Spans are "label" / "value" sized chunks, not whole lines: a gap wider than SPAN_GAP points starts a new span."""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..core.config import OCR_DPI, OCR_ENGINE

SPAN_GAP = 14.0  # points; label and value columns are further apart than this
MIN_TEXT_CHARS = 20  # fewer characters than this on a page = treat it as an image


IMAGE_COVER_OCR = 9.0  # >1 disables (Hindi-image routing is roadmap); was 0.05  # a page with an image covering at least this share of it is OCR'd even if it has a text layer
LOW_CONF = 0.6  # RapidOCR line confidence under this is treated as "probably a script it cannot read"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
TESSERACT_PATHS = [r"C:\Program Files\Tesseract-OCR	esseract.exe", r"C:\Program Files (x86)\Tesseract-OCR	esseract.exe"]


class EngineUnavailable(RuntimeError):
    pass


@dataclass
class Span:
    text: str
    page: int
    bbox: list[float]  # [x0, y0, x1, y1], 0-1, origin top-left
    conf: float = 1.0
    source: str = "textlayer"


@dataclass
class OcrResult:
    spans: list[Span] = field(default_factory=list)
    pages: int = 0
    engines: dict[int, str] = field(default_factory=dict)  # page -> engine(s) that produced it
    scripts: dict[int, str] = field(default_factory=dict)  # page -> "devanagari" when Hindi text was detected
    notes: list[str] = field(default_factory=list)

    @property
    def has_text_layer(self) -> bool:
        return any(e == "textlayer" for e in self.engines.values())

    def page_text(self, page: int) -> str:
        return "\n".join(s.text for s in self.spans if s.page == page)


# ---------------------------------------------------------------------------------------------
def _textlayer_page(pl_page, page_no: int) -> list[Span]:
    # the diagonal SPECIMEN watermark is oversized text (40+ pt vs <= 15 pt for form text): leave it out so its letters never merge into field values
    pl_page = pl_page.filter(lambda o: o.get("object_type") != "char" or o.get("size", 0) <= 30)
    words = pl_page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
    w, h = float(pl_page.width), float(pl_page.height)
    words.sort(key=lambda x: (round(x["top"] / 4), x["x0"]))
    spans: list[Span] = []
    cur: list[dict] = []

    def flush():
        if cur:
            spans.append(Span(" ".join(c["text"] for c in cur), page_no,
                              [round(min(c["x0"] for c in cur) / w, 4), round(min(c["top"] for c in cur) / h, 4),
                               round(max(c["x1"] for c in cur) / w, 4), round(max(c["bottom"] for c in cur) / h, 4)]))
            cur.clear()

    for wd in words:
        if cur and (abs(wd["top"] - cur[-1]["top"]) > 3 or wd["x0"] - cur[-1]["x1"] > SPAN_GAP):
            flush()
        cur.append(wd)
    flush()
    return spans


@lru_cache(maxsize=1)
def _rapid():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as e:  # pragma: no cover
        raise EngineUnavailable(f"rapidocr-onnxruntime not importable: {e}") from e
    return RapidOCR()


def _render(pdf_path: Path, page_index: int):
    import pypdfium2 as pdfium

    return pdfium.PdfDocument(str(pdf_path))[page_index].render(scale=OCR_DPI / 72).to_pil().convert("RGB")


def _rapid_page(img, page_no: int) -> list[Span]:
    import numpy as np

    result, _ = _rapid()(np.asarray(img))
    w, h = img.size
    out = []
    for box, text, conf in result or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        out.append(Span(text.strip(), page_no, [round(min(xs) / w, 4), round(min(ys) / h, 4), round(max(xs) / w, 4), round(max(ys) / h, 4)],
                        float(conf), "rapidocr"))
    return out


def _tesseract_cmd() -> str | None:
    found = os.getenv("TESSERACT_CMD") or shutil.which("tesseract") or next((p for p in TESSERACT_PATHS if os.path.exists(p)), None)
    return found


def tesseract_langs() -> list[str]:
    import pytesseract

    cmd = _tesseract_cmd()
    if not cmd:
        raise EngineUnavailable("tesseract is not installed or not on PATH (set TESSERACT_CMD)")
    pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract.get_languages(config="")


def _tesseract_page(img, page_no: int, lang: str = "hin+eng") -> list[Span]:
    import pytesseract

    langs = tesseract_langs()
    want = [x for x in lang.split("+") if x in langs]
    if not want:
        raise EngineUnavailable(f"tesseract has none of the languages {lang} (installed: {langs})")
    data = pytesseract.image_to_data(img, lang="+".join(want), output_type=pytesseract.Output.DICT)
    w, h = img.size
    lines: dict[tuple, list[int]] = {}
    for i, t in enumerate(data["text"]):
        if t.strip() and float(data["conf"][i]) >= 0:
            lines.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(i)
    out = []
    for idx in lines.values():
        x0, y0 = min(data["left"][i] for i in idx), min(data["top"][i] for i in idx)
        x1, y1 = max(data["left"][i] + data["width"][i] for i in idx), max(data["top"][i] + data["height"][i] for i in idx)
        out.append(Span(" ".join(data["text"][i].strip() for i in idx), page_no, [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)],
                        sum(float(data["conf"][i]) for i in idx) / len(idx) / 100, "tesseract"))
    return out


_ENGINES = {"rapidocr": _rapid_page, "tesseract": _tesseract_page}


def _inside(inner: list[float], outer: list[float], slack=0.004) -> bool:
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] - slack <= cx <= outer[2] + slack and outer[1] - slack <= cy <= outer[3] + slack


def _needs_hindi(spans: list[Span]) -> bool:
    """RapidOCR (Latin + Chinese models) cannot read Devanagari; it returns low-confidence junk or nothing for it."""
    if any(DEVANAGARI.search(s.text) for s in spans):
        return True
    low = [s for s in spans if s.conf < LOW_CONF]
    return len(low) >= 3 or (spans and len(low) / len(spans) > 0.3)


def _ocr_page(path: Path, i: int, n: int, chain: list[str], res: "OcrResult"):
    img = _render(path, i)
    spans, used = [], "none"
    for name in chain:
        try:
            spans = _ENGINES[name](img, n)
        except EngineUnavailable as e:
            res.notes.append(str(e))
            continue
        used = name
        break
    else:
        res.notes.append(f"page {n}: no engine produced text")
    if used == "rapidocr" and "tesseract" in chain + ["tesseract"] and _needs_hindi(spans):
        try:  # script routing: Hindi page -> Tesseract hin+eng
            ts = _tesseract_page(img, n)
            if any(DEVANAGARI.search(s.text) for s in ts):
                spans, used = ts, "tesseract(hin+eng)"
        except EngineUnavailable as e:
            res.notes.append(f"page {n}: looks like Devanagari but Hindi OCR is unavailable ({e})")
            spans = [s for s in spans if s.conf >= LOW_CONF]  # drop the junk rather than store it as facts
    return spans, used


def read_document(path: str | Path, engine: str | None = None) -> OcrResult:
    """Spans for every page of a PDF. Images (photos) are not OCR'd."""
    engine = (engine or OCR_ENGINE).lower()
    path = Path(path)
    res = OcrResult()
    if path.suffix.lower() != ".pdf":
        res.notes.append("image file: no OCR")
        return res
    import pdfplumber

    chain = {"auto": ["rapidocr", "tesseract"], "textlayer": [], "rapidocr": ["rapidocr"], "tesseract": ["tesseract"]}[engine]
    with pdfplumber.open(path) as pdf:
        res.pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            n = i + 1
            text_spans = _textlayer_page(page, n) if engine in ("auto", "textlayer") else []
            has_text = sum(len(s.text) for s in text_spans) >= MIN_TEXT_CHARS
            cover = sum(max(0, im["x1"] - im["x0"]) * max(0, im["bottom"] - im["top"]) for im in page.images) / float(page.width * page.height)
            if has_text and cover < IMAGE_COVER_OCR:
                res.spans += text_spans
                res.engines[n] = "textlayer"
                continue
            ocr_spans, used = _ocr_page(path, i, n, chain, res)
            if has_text:  # mixed page: keep the exact text layer, add OCR only where the text layer has nothing
                ocr_spans = [o for o in ocr_spans if not any(_inside(o.bbox, t.bbox) for t in text_spans)]
                used = f"textlayer+{used}" if used != "none" else "textlayer"
                ocr_spans = text_spans + ocr_spans
            res.spans += ocr_spans
            res.engines[n] = used
            if any(DEVANAGARI.search(s.text) for s in ocr_spans):
                res.scripts[n] = "devanagari"
    return res


def engine_status() -> dict:
    """Which OCR engines work on this machine (used by /system/ocr and the README)."""
    out = {"configured": OCR_ENGINE, "textlayer": {"available": True, "via": "pdfplumber"}}
    for name, probe in (("rapidocr", _rapid), ("tesseract", lambda: _tesseract_page(__import__("PIL.Image", fromlist=["x"]).new("RGB", (40, 20), "white"), 1))):
        try:
            probe()
            out[name] = {"available": True}
        except Exception as e:
            out[name] = {"available": False, "reason": str(e)[:160]}
    return out
