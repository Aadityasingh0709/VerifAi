"""SQLite persistence via SQLAlchemy Core (lightweight)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Audit(Base):
    __tablename__ = "audits"

    audit_id = Column(String, primary_key=True)
    document_title = Column(String, nullable=False)
    document_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="processing")
    stage = Column(String, nullable=False, default="queued")
    progress_percent = Column(Integer, nullable=False, default=0)
    claims_processed = Column(Integer, nullable=False, default=0)
    total_claims = Column(Integer, nullable=False, default=0)
    result_json = Column(Text, nullable=True)  # serialized AuditResult


Base.metadata.create_all(bind=engine)

# In-memory live state so the frontend sees progress without hitting DB every poll.
_LIVE_LOCK = threading.Lock()
_LIVE: Dict[str, dict] = {}


def put_live(audit_id: str, data: dict) -> None:
    with _LIVE_LOCK:
        _LIVE[audit_id] = data


def get_live(audit_id: str) -> Optional[dict]:
    with _LIVE_LOCK:
        return _LIVE.get(audit_id)


def update_live(audit_id: str, **patch) -> None:
    with _LIVE_LOCK:
        if audit_id in _LIVE:
            _LIVE[audit_id].update(patch)


def persist_final(audit_id: str, result: dict) -> None:
    """Persist the terminal AuditResult to SQLite."""
    with SessionLocal() as s:
        row = s.get(Audit, audit_id)
        if row is None:
            row = Audit(audit_id=audit_id, document_title=result.get("document_title", "Untitled"),
                        document_text=result.get("document_text", ""),
                        created_at=datetime.now(timezone.utc))
            s.add(row)
        row.status = result.get("status", "complete")
        row.stage = result.get("stage", "complete")
        row.progress_percent = result.get("progress_percent", 100)
        row.claims_processed = result.get("claims_processed", 0)
        row.total_claims = result.get("total_claims", 0)
        row.result_json = json.dumps(result)
        s.commit()


def load_final(audit_id: str) -> Optional[dict]:
    with SessionLocal() as s:
        row = s.get(Audit, audit_id)
        if row is None or not row.result_json:
            return None
        return json.loads(row.result_json)


def create_initial(audit_id: str, document_title: str, document_text: str) -> None:
    """Create a DB row + live state for a new audit."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        row = Audit(
            audit_id=audit_id,
            document_title=document_title,
            document_text=document_text,
            created_at=now,
            status="processing",
            stage="queued",
            progress_percent=0,
            claims_processed=0,
            total_claims=0,
        )
        s.add(row)
        s.commit()
    put_live(audit_id, {
        "audit_id": audit_id,
        "document_title": document_title,
        "document_text": document_text,
        "created_at": now.isoformat(),
        "status": "processing",
        "stage": "queued",
        "progress_percent": 0,
        "claims_processed": 0,
        "total_claims": 0,
        "claims": [],
    })
