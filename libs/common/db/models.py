"""SQLAlchemy ORM models for all database entities."""

import uuid
from datetime import datetime, timezone
import enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Enum as SAEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class RunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class ScreeningRoute(str, enum.Enum):
    NO_CLEARANCE_REQUIRED = "NO_CLEARANCE_REQUIRED"
    CATEGORY_B_STATE = "CATEGORY_B_STATE"
    CATEGORY_A_CENTRAL = "CATEGORY_A_CENTRAL"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    project_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(
        SAEnum(RunStatus, name="run_status_enum", native_enum=False),
        nullable=False,
        default=RunStatus.QUEUED,
        index=True,
    )
    route = Column(
        SAEnum(ScreeningRoute, name="screening_route_enum", native_enum=False),
        nullable=True,
        index=True,
    )
    result_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    prompt_versions_json = Column(JSON, nullable=True)
    index_version = Column(String(64), nullable=True)
    cost_usd = Column(Float, default=0.0, nullable=False)
    tokens_prompt = Column(Integer, default=0, nullable=False)
    tokens_completion = Column(Integer, default=0, nullable=False)
    degraded = Column(Boolean, default=False, nullable=False)
    worker_id = Column(String(128), nullable=True)
    task_id = Column(String(128), nullable=True, index=True)

    steps = relationship("RunStep", back_populates="run", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_runs_client_status", "client_id", "status"),
        Index("idx_runs_created_at", "created_at"),
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(64), nullable=False)
    agent = Column(String(64), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    latency_ms = Column(Float, nullable=True)
    tokens_prompt = Column(Integer, default=0, nullable=False)
    tokens_completion = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    tool_calls_json = Column(JSON, nullable=True)
    retrieved_passage_ids = Column(JSON, nullable=True)
    prompt_version = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="SUCCESS")
    error = Column(Text, nullable=True)

    run = relationship("Run", back_populates="steps")

    __table_args__ = (
        Index("idx_run_steps_run_agent", "run_id", "agent"),
    )


class Quarantine(Base):
    __tablename__ = "quarantine"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = Column(String(64), nullable=False, index=True)
    raw_payload_json = Column(JSON, nullable=False)
    field_errors_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    client_ip = Column(String(64), nullable=True)


class ClauseIndex(Base):
    __tablename__ = "clause_index"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String(64), nullable=False, index=True)
    chunk_ids_json = Column(JSON, nullable=False)
    doc_id = Column(String(64), nullable=False, index=True)
    doc_title = Column(String(255), nullable=False)
    clause_ref = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    index_version = Column(String(64), nullable=False, index=True)

    __table_args__ = (
        Index("idx_clause_id_version", "identifier", "index_version"),
    )


class CrossRefIndex(Base):
    __tablename__ = "cross_ref_index"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_chunk_id = Column(String(64), nullable=False, index=True)
    target_chunk_id = Column(String(64), nullable=False, index=True)
    ref_type = Column(String(64), nullable=False)
    ref_text = Column(Text, nullable=False)
    index_version = Column(String(64), nullable=False, index=True)

    __table_args__ = (
        Index("idx_cross_ref_source_target", "source_chunk_id", "target_chunk_id"),
    )


class IndexManifest(Base):
    __tablename__ = "index_manifest"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    built_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    doc_count = Column(Integer, nullable=False)
    chunk_count = Column(Integer, nullable=False)
    embedding_model = Column(String(128), nullable=False)
    embedding_version = Column(String(64), nullable=False)
    index_version = Column(String(64), nullable=False, unique=True, index=True)
    throughput_chunks_per_sec = Column(Float, nullable=False, default=0.0)
    source_hashes_json = Column(JSON, nullable=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    satisfactory = Column(Boolean, nullable=False)
    reason = Column(Text, nullable=True)
    category = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    run = relationship("Run", back_populates="feedbacks")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), nullable=True, index=True)
    scenario_id = Column(String(128), nullable=False, index=True)
    prompt_variant = Column(String(64), nullable=False)
    groundedness = Column(Float, nullable=True)
    context_relevance = Column(Float, nullable=True)
    faithfulness = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    route_correct = Column(Boolean, nullable=True)
    citation_recall = Column(Float, nullable=True)
    is_correct_escalation = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    scored_at = Column(DateTime(timezone=True), nullable=True)
