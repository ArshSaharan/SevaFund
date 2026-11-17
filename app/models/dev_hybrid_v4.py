"""Development-only persistence for hybrid v4 workflow records (feature flag SEVAFUND_DEV_HYBRID_V4).

Imported only by the integration, so the table exists only once the flag has been used; it is created on first use.
"""
import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class DevHybridV4Record(Base):
    __tablename__ = "dev_hybrid_v4_records"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, unique=True, index=True)
    state = Column(String(48), nullable=False)
    decision = Column(String(32), nullable=False)
    policy_version = Column(String(32), nullable=False)
    record_json = Column(Text, nullable=False)              # hybrid v4 workflow Record, including its audit log
    decision_json = Column(Text, nullable=False)            # HybridV4Decision: explanation, findings, evidence
    previous_records_json = Column(Text, default="[]")      # earlier records replaced by re-verification
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
