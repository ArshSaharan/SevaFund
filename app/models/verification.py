import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class VerificationAudit(Base):
    __tablename__ = "verification_audits"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    
    overall_score = Column(Float, nullable=False)  # 0 to 100
    risk_level = Column(String(32), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    recommendation = Column(String(32), nullable=False) # AUTO_APPROVE, FLAG_FOR_REVIEW, REJECT, NEEDS_MORE_INFO
    
    # Sub-dimension scores (each 0 - 100)
    plausibility_score = Column(Float, nullable=False)
    specificity_score = Column(Float, nullable=False)
    red_flag_score = Column(Float, nullable=False)
    documentation_score = Column(Float, nullable=False)
    
    summary = Column(Text, nullable=False)
    detailed_analysis_json = Column(Text, nullable=False)
    model_name = Column(String(64), default="crowdfund-trust-v1")
    
    # Human Trust & Safety Admin Review
    admin_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="verifications")
