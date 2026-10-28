"""Simulated source checks (prototype): QR vs printed text, digital-signature status, and a mock issuer / DigiLocker lookup
backed by data/mock_registry.json. Every row is stored with simulated=True and labelled "Simulated source (prototype)"."""
import io
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pikepdf
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[4]
REGISTRY = ROOT / "data" / "mock_registry.json"


def _sq(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else []


def decode_qr(pdf_path: Path) -> dict | None:
    page = pdfium.PdfDocument(str(pdf_path))[0]
    for scale in (3, 2):
        img = np.asarray(page.render(scale=scale).to_pil().convert("RGB"))
        for det in (cv2.QRCodeDetectorAruco(), cv2.QRCodeDetector()):  # the Aruco-based detector is the more reliable one
            data = det.detectAndDecode(img)[0]
            if data:
                try:
                    return json.loads(data)
                except ValueError:
                    return None
    return None


def signature_state(pdf_path: Path) -> dict:
    """none | valid | modified_after_signing | broken, plus the signals forensics reuses."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    raw = pdf_path.read_bytes()
    info = {"state": "none", "revisions": raw.count(b"%%EOF"), "producer": None}
    try:
        with pikepdf.open(io.BytesIO(raw)) as pk:
            info["producer"] = str(pk.docinfo.get("/Producer", "")) or None
    except Exception:
        pass
    sigs = PdfFileReader(io.BytesIO(raw)).embedded_signatures
    if not sigs:
        return info
    st = validate_pdf_signature(sigs[0])
    if not st.intact:
        info["state"] = "broken"
    elif st.modification_level.value > 0:
        info["state"] = "modified_after_signing"
    else:
        info["state"] = "valid"
    return info
