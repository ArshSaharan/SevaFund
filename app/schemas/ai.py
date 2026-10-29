from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DimensionScores(BaseModel):
    plausibility: float = Field(..., description="Cost & medical/factual plausibility score (0-100)")
    specificity: float = Field(..., description="Presence of verifiable concrete facts & details (0-100)")
    red_flag_score: float = Field(..., description="Absence of known scam markers/high-pressure tactics (0-100)")
    documentation: float = Field(..., description="Evidence & proof completeness score (0-100)")

class BenchmarkComparison(BaseModel):
    category: str
    item_detected: Optional[str] = None
    requested_amount: float
    typical_range_min: float
    typical_range_max: float
    currency: str = "INR"
    ratio_to_benchmark: float
    benchmark_status: str  # "WITHIN_NORMAL_RANGE", "SLIGHTLY_ELEVATED", "SUSPICIOUSLY_EXCESSIVE", "UNCATALOGED"
    insight: str

class VerificationResult(BaseModel):
    authenticity_score: float = Field(..., description="Overall calculated authenticity score from 0 to 100")
    risk_level: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    recommendation: str = Field(..., description="AUTO_APPROVE, FLAG_FOR_REVIEW, REJECT, NEEDS_MORE_INFO")
    summary: str
    dimension_scores: DimensionScores
    cost_benchmark: Optional[BenchmarkComparison] = None
    red_flags: List[str] = []
    positive_signals: List[str] = []
    missing_requirements: List[str] = []
    confidence: float = 0.95
    model_used: str = "crowdfund-trust-v1"

class StoryEnhanceRequest(BaseModel):
    category: str
    goal_amount: float
    rough_notes: str
    beneficiary_name: Optional[str] = None
    target_audience: Optional[str] = "Community & Friends"

class StoryEnhanceResponse(BaseModel):
    suggested_title: str
    suggested_subtitle: str
    structured_story: str
    recommended_itemized_breakdown: List[Dict[str, Any]]
    transparency_tips: List[str]
    suggested_tags: List[str]

class CostBenchmarkRequest(BaseModel):
    category: str
    description: str
    requested_amount: float

class VerificationPreCheckRequest(BaseModel):
    title: str
    category: str
    story: str
    goal_amount: float
    beneficiary_name: Optional[str] = None
    beneficiary_type: Optional[str] = "SELF"
    city: Optional[str] = None
    state: Optional[str] = None
    has_documents: bool = False
    documents: Optional[List[Dict[str, Any]]] = None
