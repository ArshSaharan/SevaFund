import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.ai import VerificationResult

class ProofDocumentSchema(BaseModel):
    doc_type: str = Field(..., description="HOSPITAL_ESTIMATE, DISCHARGE_SUMMARY, AYUSHMAN_CARD, AADHAAR, PAN, FEE_STRUCTURE")
    title: str
    file_url: str
    verified: bool = False

class CampaignCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    subtitle: Optional[str] = None
    category: str = Field(..., description="MEDICAL, EMERGENCY, EDUCATION, COMMUNITY, MEMORIAL, ANIMALS, OTHER")
    story: str = Field(..., min_length=20)
    goal_amount: float = Field(..., gt=0, description="Target funding amount in Indian Rupees (INR - ₹)")
    cover_image_url: Optional[str] = None
    country: str = "IN"
    state: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = Field(None, description="6-digit Indian PIN code")
    beneficiary_type: str = "SELF"  # SELF, FAMILY, FRIEND, NGO_TRUST
    beneficiary_name: Optional[str] = None
    relationship_to_beneficiary: Optional[str] = None
    hospital_name: Optional[str] = Field(None, description="e.g. AIIMS New Delhi, Tata Memorial, Apollo, Fortis")
    hospital_patient_uhid: Optional[str] = Field(None, description="Patient Unique Hospital Identification / OPD number")
    is_80g_tax_exempt: bool = False
    direct_hospital_transfer: bool = False
    proof_documents: Optional[List[ProofDocumentSchema]] = None
    deadline: Optional[datetime.datetime] = None

class CampaignUpdateSchema(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    story: Optional[str] = None
    goal_amount: Optional[float] = None
    cover_image_url: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_patient_uhid: Optional[str] = None
    deadline: Optional[datetime.datetime] = None

class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int
    title: str
    subtitle: Optional[str] = None
    category: str
    story: str
    goal_amount: float
    current_amount: float
    currency: str = "INR"
    donor_count: int
    percent_funded: float
    cover_image_url: Optional[str] = None
    country: str = "IN"
    state: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    beneficiary_type: str
    beneficiary_name: Optional[str] = None
    relationship_to_beneficiary: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_patient_uhid: Optional[str] = None
    is_80g_tax_exempt: bool = False
    direct_hospital_transfer: bool = False
    status: str
    proof_documents: Optional[List[Dict[str, Any]]] = None
    
    # AI badge & score
    authenticity_score: Optional[float] = None
    risk_level: Optional[str] = None
    ai_recommendation: Optional[str] = None
    ai_verified_at: Optional[datetime.datetime] = None
    
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deadline: Optional[datetime.datetime] = None

class CampaignListResponse(BaseModel):
    items: List[CampaignResponse]
    total: int
    page: int
    limit: int

class AdminDecisionRequest(BaseModel):
    decision: str = Field(..., description="APPROVE, REJECT, REQUEST_MORE_INFO")
    notes: Optional[str] = None
