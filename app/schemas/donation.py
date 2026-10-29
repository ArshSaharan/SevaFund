import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class DonationCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Donation amount in Indian Rupees (INR - ₹)")
    tip_amount: float = Field(default=0.0, ge=0, description="Optional voluntary platform tip")
    donor_name: Optional[str] = "Kind Supporter"
    donor_email: Optional[str] = None
    donor_phone: Optional[str] = Field(None, description="10-digit Indian mobile number")
    donor_pan: Optional[str] = Field(None, description="10-digit PAN card for 80G tax exemption receipt")
    support_message: Optional[str] = None
    is_anonymous: bool = False
    payment_method: Optional[str] = "UPI"  # UPI, NETBANKING, DEBIT_CARD, CREDIT_CARD, RAZORPAY
    upi_id: Optional[str] = Field(None, description="e.g. user@okhdfcbank, user@paytm")
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    gateway_signature: Optional[str] = None

class CreateGatewayOrderRequest(BaseModel):
    campaign_id: int
    amount: float = Field(..., gt=0)
    currency: str = "INR"

class CreateGatewayOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str = "INR"
    key_id: str
    campaign_id: int
    campaign_title: str
    beneficiary_name: Optional[str] = None

class DonationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    donor_id: Optional[int] = None
    donor_name: str
    amount: float
    tip_amount: float
    fee_amount: float
    net_amount: float
    currency: str = "INR"
    payment_method: str
    upi_id: Optional[str] = None
    tax_exemption_80g_number: Optional[str] = None
    support_message: Optional[str] = None
    is_anonymous: bool
    payment_status: str
    transaction_ref: Optional[str] = None
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    created_at: datetime.datetime

class DonationReceipt(BaseModel):
    transaction_ref: str
    campaign_id: int
    campaign_title: str
    donor_name: str
    amount: float
    tip_amount: float
    total_charged: float
    currency: str = "INR"
    payment_method: str
    tax_exemption_80g_number: Optional[str] = None
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    timestamp: datetime.datetime
    receipt_message: str

class AdminDonationItem(BaseModel):
    id: int
    campaign_id: int
    campaign_title: str
    beneficiary_name: Optional[str] = None
    beneficiary_type: Optional[str] = None
    hospital_name: Optional[str] = None
    donor_id: Optional[int] = None
    donor_name: str
    is_anonymous: bool
    donor_email: Optional[str] = None
    donor_phone: Optional[str] = None
    donor_pan: Optional[str] = None
    amount: float
    tip_amount: float
    fee_amount: float
    net_amount: float
    currency: str = "INR"
    payment_method: str
    upi_id: Optional[str] = None
    tax_exemption_80g_number: Optional[str] = None
    support_message: Optional[str] = None
    payment_status: str
    transaction_ref: Optional[str] = None
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    created_at: datetime.datetime

class AdminDonationsSummary(BaseModel):
    total_donations_count: int
    total_amount_raised: float
    total_net_amount: float
    total_fee_amount: float
    average_donation: float

class AdminDonationsResponse(BaseModel):
    items: List[AdminDonationItem]
    total: int
    page: int
    limit: int
    summary: AdminDonationsSummary
