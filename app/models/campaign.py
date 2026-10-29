import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(255), nullable=False, index=True)
    subtitle = Column(String(500), nullable=True)
    category = Column(String(64), nullable=False, index=True)  # MEDICAL, EMERGENCY, EDUCATION, COMMUNITY, MEMORIAL, ANIMALS, OTHER
    story = Column(Text, nullable=False)
    
    # Financial targets (in INR - ₹)
    goal_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    currency = Column(String(8), default="INR")
    donor_count = Column(Integer, default=0)
    
    # Media and location in India
    cover_image_url = Column(String(512), nullable=True)
    country = Column(String(4), default="IN")
    state = Column(String(64), nullable=True)  # e.g., Maharashtra, Delhi, Karnataka
    city = Column(String(128), nullable=True)   # e.g., Mumbai, New Delhi, Bengaluru
    postal_code = Column(String(32), nullable=True) # 6-digit Indian PIN code
    
    # Beneficiary & Indian Medical Verification
    beneficiary_type = Column(String(32), default="SELF")  # SELF, FAMILY, FRIEND, NGO_TRUST
    beneficiary_name = Column(String(255), nullable=True)
    relationship_to_beneficiary = Column(String(255), nullable=True)
    hospital_name = Column(String(255), nullable=True)  # e.g., AIIMS New Delhi, Tata Memorial, Apollo
    hospital_patient_uhid = Column(String(64), nullable=True) # Unique Hospital Identification / OPD Number
    is_80g_tax_exempt = Column(Boolean, default=False)
    direct_hospital_transfer = Column(Boolean, default=False) # Pay directly to hospital trust account
    
    # Status lifecycle
    status = Column(String(32), default="PENDING_VERIFICATION", index=True) 
    # DRAFT, PENDING_VERIFICATION, ACTIVE, FLAGGED, PAUSED, COMPLETED, REJECTED
    
    # Supporting documentation (Hospital estimate letter, Discharge summary, Aadhaar, etc.)
    proof_documents_json = Column(Text, nullable=True)
    
    # AI Trust & Safety Assessment
    authenticity_score = Column(Float, nullable=True)  # 0 to 100
    risk_level = Column(String(32), nullable=True)     # LOW, MEDIUM, HIGH, CRITICAL
    ai_recommendation = Column(String(32), nullable=True) # AUTO_APPROVE, FLAG_FOR_REVIEW, REJECT, NEEDS_MORE_INFO
    ai_verified_at = Column(DateTime, nullable=True)
    
    # Dates
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    creator = relationship("User", back_populates="campaigns")
    donations = relationship("Donation", back_populates="campaign", cascade="all, delete-orphan")
    updates = relationship("CampaignUpdate", back_populates="campaign", cascade="all, delete-orphan")
    payouts = relationship("PayoutRequest", back_populates="campaign", cascade="all, delete-orphan")
    verifications = relationship("VerificationAudit", back_populates="campaign", cascade="all, delete-orphan")
