import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'storage' / 'satyapan.db'}")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", ROOT / "storage"))
# OCR_ENGINE: auto (text layer -> rapidocr -> tesseract) | textlayer | rapidocr | tesseract
OCR_ENGINE = os.getenv("OCR_ENGINE", "auto").lower()
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
USE_CLIP = os.getenv("USE_CLIP", "false").lower() == "true"

STATUSES = [
    "Verified",
    "Mismatch detected",
    "Expired",
    "Verification pending",
    "Source unavailable",
    "Manual review required",
]
