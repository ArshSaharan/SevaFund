from fastapi import APIRouter, HTTPException, status
from app.schemas.ai import (
    VerificationResult,
    VerificationPreCheckRequest,
    StoryEnhanceRequest,
    StoryEnhanceResponse,
    CostBenchmarkRequest,
    BenchmarkComparison
)
from app.services.ai_verifier import ai_verifier
from app.services.ai_assistant import ai_assistant
from app.services.fraud_detector import analyze_cost_benchmark

router = APIRouter(prefix="/ai", tags=["AI Verification & Trust Intelligence"])

@router.post("/verify-request", response_model=VerificationResult)
async def verify_request(req: VerificationPreCheckRequest):
    """
    Independent AI Verification endpoint.
    Assesses authenticity, fraud indicators, US procedure cost benchmarks,
    and missing evidence before or during campaign submission.
    """
    location = f"{req.city or ''}, {req.state or ''}".strip(", ")
    docs = req.documents or []
    
    result = await ai_verifier.verify_campaign_request(
        title=req.title,
        category=req.category,
        story=req.story,
        goal_amount=req.goal_amount,
        beneficiary_name=req.beneficiary_name,
        beneficiary_type=req.beneficiary_type,
        location=location,
        proof_documents=docs
    )
    return result

@router.post("/enhance-story", response_model=StoryEnhanceResponse)
async def enhance_story(req: StoryEnhanceRequest):
    """
    AI Story Assistant: Transforms organizer rough notes into an authentic,
    transparent 4-part fundraising pitch complete with itemized budget and trust tips.
    """
    return await ai_assistant.enhance_campaign_story(
        category=req.category,
        goal_amount=req.goal_amount,
        rough_notes=req.rough_notes,
        beneficiary_name=req.beneficiary_name,
        target_audience=req.target_audience
    )

@router.post("/benchmark-cost")
def check_cost_benchmark(req: CostBenchmarkRequest):
    """
    Validates a requested dollar amount against standard US national cost benchmarks
    for medical surgeries, cancer treatments, funeral arrangements, tuition, and pet care.
    """
    benchmark = analyze_cost_benchmark(req.category, req.description, req.requested_amount)
    if not benchmark:
        return {
            "category": req.category,
            "requested_amount": req.requested_amount,
            "benchmark_status": "UNCATALOGED",
            "insight": f"No specific standardized US benchmark table entry found for '{req.description}'. General plausibility rules apply."
        }
    return benchmark
