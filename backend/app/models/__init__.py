from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Institution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    permanent_id: str
    state: str = ""
    region: str = ""
    pincode: str = ""
    archive_only: bool = False  # filed in the previous cycle, not applying now


class Application(SQLModel, table=True):
    id: str = Field(primary_key=True)  # e.g. EoA-DEMO-0417
    institution_id: int = Field(foreign_key="institution.id")
    category: str
    academic_session: str
    submitted_at: datetime = Field(default_factory=utcnow)
    status: str = "Received"  # Received / Processing / Ready for review / Reviewed
    risk_lane: Optional[str] = None  # Green / Amber / Red
    risk_score: float = 0.0
    cycle_label: str = "Current cycle"  # "Archive · 2025 cycle" for previous-cycle files
    pipeline_stage: str = "none"  # none / extracted / checked


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    doc_type: str
    category_group: str
    filename: str
    pages: int = 1
    file_path: str
    quality_ok: bool = True
    uploaded_at: datetime = Field(default_factory=utcnow)
    kind: str = ""  # text / scan / image, set at intake
    quality_note: str = ""
    classify_confidence: float = 0.0
    ocr_engine: str = ""


class Fact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    key: str
    value: str
    normalised_value: str = ""
    page: int = 1
    bbox: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    confidence: float = 1.0


class Finding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    document_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    check_type: str
    status: str
    severity: str = "medium"
    confidence: float = 0.0
    reason: str = ""
    rule_id: str = ""
    evidence: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    how_to_clear: str = ""
    officer_action: str = "none"
    officer_note: str = ""


class SourceCheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    channel: str
    requested_at: datetime = Field(default_factory=utcnow)
    response: dict = Field(default_factory=dict, sa_column=Column(JSON))
    result: str = "Verification pending"
    simulated: bool = True


class ImageFingerprint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    institution_id: int = Field(foreign_key="institution.id", index=True)
    page_or_frame: int = 0
    phash: str
    dhash: str
    whash: str = ""
    embedding: Optional[list[float]] = Field(default=None, sa_column=Column(JSON))


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow)
    actor: str
    role: str
    action: str
    entity: str
    payload_json: str = "{}"
    prev_hash: str = ""
    hash: str = ""


class RuleSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    version: int = 1
    yaml_text: str
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
