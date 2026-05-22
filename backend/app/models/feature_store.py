import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class FeatureSchemaVersion(Base):
    __tablename__ = "feature_schema_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    schema_def: Mapped[dict] = mapped_column(JSON, nullable=False)
    features: Mapped[list] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureLineage(Base):
    __tablename__ = "feature_lineage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    replay_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_keys: Mapped[list] = mapped_column(JSON, nullable=False)
    feature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market_condition_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
