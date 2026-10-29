import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class PayoutRequest(Base):
    __tablename__ = "payout_requests"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    
    amount = Column(Float, nullable=False) # in INR (₹)
    currency = Column(String(8), default="INR")
    
    payout_method = Column(String(32), default="NEFT_IMPS_RTGS")  # NEFT_IMPS_RTGS, DIRECT_HOSPITAL_NEFT, UPI_PAYOUT
    bank_name = Column(String(128), nullable=True) # e.g. State Bank of India, HDFC Bank, ICICI Bank
    ifsc_code = Column(String(16), nullable=True)  # 11-character Indian IFSC code
    account_number_last4 = Column(String(4), nullable=True)
    upi_id = Column(String(128), nullable=True)    # If UPI payout
    beneficiary_pan = Column(String(10), nullable=True)
    
    status = Column(String(32), default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED, PAID
    review_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    campaign = relationship("Campaign", back_populates="payouts")
