import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.database import Base


class PaymentOrder(Base):
    """A Razorpay order created by this server.  A donation is recorded only against a stored order, after the
    payment is verified, and each order (and each Razorpay payment) can be recorded at most once."""
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, index=True)
    gateway_order_id = Column(String(128), nullable=False, unique=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    amount_paise = Column(Integer, nullable=False)          # donation + tip, as charged by Razorpay
    currency = Column(String(8), nullable=False, default="INR")
    receipt = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="CREATED")   # CREATED -> PAID
    gateway_payment_id = Column(String(128), nullable=True, unique=True)
    donation_id = Column(Integer, ForeignKey("donations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)
