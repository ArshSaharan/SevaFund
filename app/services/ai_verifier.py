import json
import logging
from typing import Dict, Any, List, Optional
import httpx

from app.config import settings
from app.schemas.ai import VerificationResult, DimensionScores, BenchmarkComparison
from app.services.fraud_detector import (
    analyze_cost_benchmark,
    detect_red_flags,
    extract_specificity_signals,
    format_inr
)

logger = logging.getLogger("ai_verifier")

class AIVerifierService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL

    async def verify_campaign_request(
        self,
        title: str,
        category: str,
        story: str,
        goal_amount: float,
        beneficiary_name: Optional[str] = None,
        beneficiary_type: Optional[str] = "SELF",
        location: Optional[str] = None,
        proof_documents: Optional[List[Dict[str, Any]]] = None
    ) -> VerificationResult:
        """
        Runs comprehensive authenticity, fraud detection, and plausibility verification for Indian campaigns.
        Uses Gemini AI if configured with fallback to intelligent local Indian NLP heuristic engine.
        """
        if self.api_key:
            try:
                gemini_result = await self._verify_with_gemini(
                    title=title,
                    category=category,
                    story=story,
                    goal_amount=goal_amount,
                    beneficiary_name=beneficiary_name,
                    beneficiary_type=beneficiary_type,
                    location=location,
                    proof_documents=proof_documents
                )
                if gemini_result:
                    return gemini_result
            except Exception as e:
                logger.warning(f"Gemini API verification failed or timed out, falling back to local Indian engine: {e}")

        # Local intelligent Indian verification engine
        return self._verify_with_local_heuristics(
            title=title,
            category=category,
            story=story,
            goal_amount=goal_amount,
            beneficiary_name=beneficiary_name,
            beneficiary_type=beneficiary_type,
            location=location,
            proof_documents=proof_documents
        )

    def _verify_with_local_heuristics(
        self,
        title: str,
        category: str,
        story: str,
        goal_amount: float,
        beneficiary_name: Optional[str],
        beneficiary_type: Optional[str],
        location: Optional[str],
        proof_documents: Optional[List[Dict[str, Any]]]
    ) -> VerificationResult:
        full_text = f"{title}\n{story}"
        formatted_goal = format_inr(goal_amount)
        
        # 1. Cost Benchmark Analysis & Plausibility in India (INR)
        benchmark_data = analyze_cost_benchmark(category, full_text, goal_amount)
        plausibility_score = 80.0
        
        positive_signals = []
        missing_requirements = []
        
        if benchmark_data:
            benchmark_status = benchmark_data["benchmark_status"]
            if benchmark_status == "WITHIN_NORMAL_RANGE":
                plausibility_score = 92.0
                positive_signals.append(f"Goal amount ({formatted_goal}) matches Indian hospital benchmarks for {benchmark_data['item_detected']}")
            elif benchmark_status == "SLIGHTLY_ELEVATED":
                plausibility_score = 65.0
                missing_requirements.append(
                    f"Requested amount ({formatted_goal}) is slightly above typical Indian averages. Upload signed hospital estimate letter with UHID number."
                )
            elif benchmark_status == "SUSPICIOUSLY_EXCESSIVE":
                plausibility_score = 30.0
                missing_requirements.append(
                    f"Requested amount ({formatted_goal}) is significantly higher than standard Indian hospital costs. Requires official hospital estimate signed by Medical Superintendent."
                )
        else:
            if goal_amount > 50000000:  # > 5 Crores
                plausibility_score = 40.0
                missing_requirements.append("Goal exceeds ₹5 Crores without verified NGO/institutional trust registration. Upload 80G/12A trust deed.")
            elif goal_amount < 500:
                plausibility_score = 70.0
            else:
                plausibility_score = 85.0

        # 2. Red Flags & High-Pressure Scam Detection (Personal UPI, fake promises)
        detected_flags, red_flag_penalty = detect_red_flags(full_text)
        red_flag_score = max(0.0, 100.0 - red_flag_penalty)

        # 3. Specificity and Indian Institutional Density (AIIMS, Apollo, Doctor, etc.)
        spec_signals, specificity_score = extract_specificity_signals(full_text, location)
        if len(detected_flags) >= 2:
            # When multiple scam markers are present, discount superficial specificity matches
            specificity_score = min(15.0, specificity_score * 0.2)
        else:
            positive_signals.extend(spec_signals)
        
        if specificity_score < 50.0:
            missing_requirements.append("Add specific details: hospital name (e.g. AIIMS, Apollo, Max), city, doctor's name, and UHID / Patient ID.")

        # 4. Beneficiary transparency check
        if beneficiary_type and beneficiary_type.upper() != "SELF":
            if not beneficiary_name or len(beneficiary_name.strip()) < 3:
                detected_flags.append("Fundraiser is for a third party, but patient/beneficiary name is missing.")
                red_flag_score = max(0.0, red_flag_score - 20)
                missing_requirements.append("Disclose the full name and relationship to the patient/beneficiary (e.g. Father, Mother, Daughter, Friend).")
            else:
                positive_signals.append(f"Beneficiary clearly named ({beneficiary_name}, {beneficiary_type.lower()})")

        # 5. Supporting Documentation Evaluation (Hospital estimate letter, Discharge summary, Aadhaar, etc.)
        has_docs = bool(proof_documents and len(proof_documents) > 0)
        if has_docs:
            doc_count = len(proof_documents)
            documentation_score = min(100.0, 60.0 + (doc_count * 20.0))
            positive_signals.append(f"{doc_count} supporting Indian verification document(s) attached (Hospital Estimate / ID)")
        else:
            documentation_score = 25.0
            missing_requirements.append("Upload at least one supporting document (Hospital Estimate Letter on official letterhead, Discharge Summary, or Govt ID).")

        # Composite Authenticity Score
        overall_score = (
            (plausibility_score * 0.30) +
            (specificity_score * 0.25) +
            (red_flag_score * 0.25) +
            (documentation_score * 0.20)
        )
        overall_score = round(max(5.0, min(99.0, overall_score)), 1)

        # Risk Classification & Action Recommendation
        if overall_score >= settings.AI_AUTO_APPROVE_SCORE_THRESHOLD:
            risk_level = "LOW"
            recommendation = "AUTO_APPROVE"
            summary = "Campaign exhibits high credibility, realistic Indian medical costs, and recognized hospital/institutional detail. Approved for live fundraising."
        elif overall_score >= settings.AI_REVIEW_SCORE_THRESHOLD:
            risk_level = "MEDIUM"
            recommendation = "FLAG_FOR_REVIEW"
            summary = "Campaign has moderate credibility. Hospital estimate or patient relationship details require verification by our Indian Trust & Safety team."
        elif overall_score >= 35.0:
            risk_level = "HIGH"
            recommendation = "NEEDS_MORE_INFO"
            summary = "High risk detected due to missing hospital estimate letter, vague claims, or cost discrepancies. Organizer must provide hospital bills."
        else:
            risk_level = "CRITICAL"
            recommendation = "REJECT"
            summary = "Multiple critical red flags detected (untraceable personal UPI solicitations, impossible medical claims, or missing medical records). Rejected."

        bench_obj = BenchmarkComparison(**benchmark_data) if benchmark_data else None

        return VerificationResult(
            authenticity_score=overall_score,
            risk_level=risk_level,
            recommendation=recommendation,
            summary=summary,
            dimension_scores=DimensionScores(
                plausibility=round(plausibility_score, 1),
                specificity=round(specificity_score, 1),
                red_flag_score=round(red_flag_score, 1),
                documentation=round(documentation_score, 1)
            ),
            cost_benchmark=bench_obj,
            red_flags=detected_flags,
            positive_signals=positive_signals,
            missing_requirements=missing_requirements,
            confidence=0.94,
            model_used="crowdfund-india-trust-v1"
        )

    async def _verify_with_gemini(
        self,
        title: str,
        category: str,
        story: str,
        goal_amount: float,
        beneficiary_name: Optional[str],
        beneficiary_type: Optional[str],
        location: Optional[str],
        proof_documents: Optional[List[Dict[str, Any]]]
    ) -> Optional[VerificationResult]:
        """
        Invokes Gemini API for deep natural language authenticity assessment within the Indian healthcare & charity context.
        """
        formatted_goal = format_inr(goal_amount)
        prompt = f"""
You are the Chief Trust & Safety AI Auditor for an Indian Crowdfunding platform (similar to Milaap, Ketto, and ImpactGuru).
Analyze the following Indian crowdfunding campaign request in Indian Rupees (INR) for authenticity, plausibility, and fraud risk.

CAMPAIGN DETAILS:
- Title: {title}
- Category: {category}
- Requested Goal: {formatted_goal} (INR)
- Beneficiary Type: {beneficiary_type}
- Beneficiary Name: {beneficiary_name or 'Not specified'}
- Location: {location or 'Not specified'}
- Story / Pitch:
{story}
- Documents Attached: {len(proof_documents or [])} documents.

EVALUATE FOR INDIA:
1. Plausibility (0-100): Is the requested amount in INR realistic compared to typical Indian hospital treatment costs (AIIMS, Tata Memorial, Apollo, Fortis, etc.)?
2. Specificity (0-100): Are there real Indian hospital names, attending doctor names, medical terms, UHID/OPD numbers, and dates?
3. Red Flag Safety (0-100): Is it free of scam pressure, requests for direct personal UPI transfers, fake stamps, or unverified Ayurvedic cancer cures?
4. Documentation (0-100): Are hospital estimate letters or medical reports cited or uploaded?

Respond ONLY with a JSON object matching this schema:
{{
  "authenticity_score": float (0 to 100),
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "recommendation": "AUTO_APPROVE" | "FLAG_FOR_REVIEW" | "NEEDS_MORE_INFO" | "REJECT",
  "summary": "Brief 2-3 sentence executive evaluation tailored to Indian medical context",
  "dimension_scores": {{
    "plausibility": float,
    "specificity": float,
    "red_flag_score": float,
    "documentation": float
  }},
  "red_flags": ["list", "of", "issues"],
  "positive_signals": ["list", "of", "credible", "facts"],
  "missing_requirements": ["list", "of", "missing", "documents"]
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                
                bench = analyze_cost_benchmark(category, f"{title}\n{story}", goal_amount)
                bench_obj = BenchmarkComparison(**bench) if bench else None

                return VerificationResult(
                    authenticity_score=float(parsed["authenticity_score"]),
                    risk_level=parsed["risk_level"],
                    recommendation=parsed["recommendation"],
                    summary=parsed["summary"],
                    dimension_scores=DimensionScores(**parsed["dimension_scores"]),
                    cost_benchmark=bench_obj,
                    red_flags=parsed.get("red_flags", []),
                    positive_signals=parsed.get("positive_signals", []),
                    missing_requirements=parsed.get("missing_requirements", []),
                    confidence=0.96,
                    model_used=self.model
                )
        return None

ai_verifier = AIVerifierService()
