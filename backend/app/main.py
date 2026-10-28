from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import applications, dashboard, pages, system, workspace
from .core.db import init_db

app = FastAPI(title="Satyapan API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"ok": True, "prototype": True, "data": "synthetic"}


app.include_router(dashboard.router)
app.include_router(applications.router)
app.include_router(system.router)
app.include_router(workspace.router)
app.include_router(pages.router)
