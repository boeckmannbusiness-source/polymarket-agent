from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class RemoteControlAudit(Base):
    __tablename__ = "remote_control_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    telegram_user = Column(String(255), nullable=False)
    command = Column(String(255), nullable=False)
    result = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)
