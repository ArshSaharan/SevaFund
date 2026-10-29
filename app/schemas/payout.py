import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class PayoutCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to withdraw from campaign funds in INR (₹)")
    bank_name: str = Field(..., min_length=2, description="Indian Bank Name (e.g. State Bank of India, HDFC Bank, ICICI Bank)")
    ifsc_code: str = Field(..., min_length=11, max_length=11, description="11-character Indian IFSC code (e.g. SBIN0001234)")
    account_number: str = Field(..., min_length=9, max_length=18, description="Indian Bank Account number")
    payout_method: Optional[str] = "NEFT_IMPS_RTGS" # NEFT_IMPS_RTGS, DIRECT_HOSPITAL_NEFT, UPI_PAYOUT
    upi_id: Optional[str] = Field(None, description="UPI ID if opting for UPI payout")
    beneficiary_pan: Optional[str] = Field(None, description="10-digit PAN of recipient for TDS/Income Tax records")

class PayoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    amount: float
    currency: str = "INR"
    payout_method: str
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    account_number_last4: Optional[str] = None
    upi_id: Optional[str] = None
    beneficiary_pan: Optional[str] = None
    status: str
    review_notes: Optional[str] = None
    created_at: datetime.datetime
    processed_at: Optional[datetime.datetime] = None
