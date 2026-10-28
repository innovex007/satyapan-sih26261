"""Production entry point – one server for the whole prototype (used by the Dockerfile).
   /api/...      -> the existing FastAPI backend, unchanged
   everything else -> the built React website (frontend/dist)
It also puts the demo data back to its clean state after IDLE_RESET_MIN minutes without visitors,
so one judge's clicks (e.g. a Dispose or an accepted flag) never spoil the demo for the next one.
Run from the backend folder:  uvicorn serve:web --host 0.0.0.0 --port 7860"""
import inspect
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.main import app as api

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
PORT = int(os.getenv("PORT", "7860"))
IDLE_RESET_MIN = float(os.getenv("IDLE_RESET_MIN", "15"))

web = FastAPI(title="prototype", docs_url=None, redoc_url=None)
web.mount("/api", api)
web.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

RESET = "satyapan"
_state = {"last": time.time(), "dirty": False}


@web.middleware("http")
async def _track(request: Request, call_next):
    _state["last"] = time.time()
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        _state["dirty"] = True
    return await call_next(request)


def reset_demo():
    """Project-specific clean-state restore (see RESET below)."""
    if RESET == "ekatra":
        import sqlite3
        src, dst = sqlite3.connect(ROOT / "data" / "ekatra.clean.db"), sqlite3.connect(ROOT / "data" / "ekatra.db", timeout=30)
        src.backup(dst); src.close(); dst.close()
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/api/admin/reload", method="POST"), timeout=20)
        except Exception as e:  # noqa: BLE001
            print("reload after reset failed:", e)
    elif RESET == "satyapan":
        subprocess.call([sys.executable, str(ROOT / "data" / "reset_demo.py")], cwd=ROOT)


def _idle_reset_loop():
    while True:
        time.sleep(60)
        if _state["dirty"] and time.time() - _state["last"] > IDLE_RESET_MIN * 60:
            try:
                reset_demo()
                print("demo data reset after idle period")
            except Exception as e:  # noqa: BLE001
                print("demo reset failed:", e)
            _state["dirty"] = False


@web.on_event("startup")
async def _start():
    for h in api.router.on_startup:  # mounted apps don't receive startup events – run the backend's own
        r = h()
        if inspect.isawaitable(r):
            await r
    if IDLE_RESET_MIN > 0:
        threading.Thread(target=_idle_reset_loop, daemon=True).start()


@web.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    f = (DIST / path).resolve()
    if path and f.is_file() and DIST.resolve() in f.parents:
        return FileResponse(f)
    return FileResponse(DIST / "index.html")
