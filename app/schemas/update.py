import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class UpdateCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=10)
    image_url: Optional[str] = None
    receipt_evidence_url: Optional[str] = None

class UpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    title: str
    content: str
    image_url: Optional[str] = None
    receipt_evidence_url: Optional[str] = None
    created_at: datetime.datetime
