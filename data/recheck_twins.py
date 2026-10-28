"""Re-run the checks (not extraction) for the applications that have twin findings, e.g. after changing the finding wording."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.models import Application, Finding  # noqa: E402
from app.pipeline.checks.rules import run_checks  # noqa: E402

with Session(engine) as s:
    ids = sorted({f.application_id for f in s.exec(select(Finding).where(Finding.check_type == "twin")).all()})
    for i in ids:
        n = len(run_checks(s, s.get(Application, i)))
        print(i, n, "findings")
print("rechecked", len(ids), "applications")
