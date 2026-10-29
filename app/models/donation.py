import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    donor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null if guest donor
    
    donor_name = Column(String(255), default="Kind Supporter")
    donor_email = Column(String(255), nullable=True)
    donor_phone = Column(String(32), nullable=True)
    donor_pan = Column(String(10), nullable=True) # Indian Permanent Account Number for IT compliance
    
    amount = Column(Float, nullable=False)       # in INR (₹)
    tip_amount = Column(Float, default=0.0)      # Voluntary platform tip
    fee_amount = Column(Float, default=0.0)      # Gateway fee
    net_amount = Column(Float, nullable=False)   # Net received by campaign
    currency = Column(String(8), default="INR")
    
    payment_method = Column(String(32), default="UPI") # UPI, NETBANKING, DEBIT_CARD, CREDIT_CARD
    upi_id = Column(String(128), nullable=True)        # e.g., user@okhdfcbank
    tax_exemption_80g_number = Column(String(64), nullable=True) # 80G tax receipt number
    
    support_message = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False)
    payment_status = Column(String(32), default="COMPLETED")  # PENDING, COMPLETED, FAILED, REFUNDED
    transaction_ref = Column(String(128), nullable=True, unique=True)
    gateway_order_id = Column(String(128), nullable=True)
    gateway_payment_id = Column(String(128), nullable=True)
    gateway_signature = Column(String(256), nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="donations")
    donor = relationship("User", back_populates="donations")
