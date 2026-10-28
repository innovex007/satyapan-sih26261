from fastapi import APIRouter

from ..pipeline.ocr import engine_status

router = APIRouter(tags=["system"])


@router.get("/system/ocr")
def ocr_status():
    return engine_status()
