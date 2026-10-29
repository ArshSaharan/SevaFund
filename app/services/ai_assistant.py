import logging
from typing import Dict, Any, List, Optional
import httpx
import json

from app.config import settings
from app.schemas.ai import StoryEnhanceResponse
from app.services.fraud_detector import analyze_cost_benchmark, format_inr

logger = logging.getLogger("ai_assistant")

class AIAssistantService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL

    async def enhance_campaign_story(
        self,
        category: str,
        goal_amount: float,
        rough_notes: str,
        beneficiary_name: Optional[str] = None,
        target_audience: Optional[str] = "Community & Friends"
    ) -> StoryEnhanceResponse:
        """
        Transforms rough notes into a transparent, trustworthy, well-structured Indian crowdfunding campaign story.
        """
        if self.api_key:
            try:
                llm_response = await self._enhance_with_gemini(
                    category=category,
                    goal_amount=goal_amount,
                    rough_notes=rough_notes,
                    beneficiary_name=beneficiary_name,
                    target_audience=target_audience
                )
                if llm_response:
                    return llm_response
            except Exception as e:
                logger.warning(f"Gemini API story enhancer failed, using local Indian builder: {e}")

        # Local intelligent Indian generator
        return self._enhance_with_local_templates(
            category=category,
            goal_amount=goal_amount,
            rough_notes=rough_notes,
            beneficiary_name=beneficiary_name
        )

    def _enhance_with_local_templates(
        self,
        category: str,
        goal_amount: float,
        rough_notes: str,
        beneficiary_name: Optional[str]
    ) -> StoryEnhanceResponse:
        name = beneficiary_name or "our family member"
        cat_title = category.capitalize()
        formatted_goal = format_inr(goal_amount)
        
        suggested_title = f"Help {name} Fight Through {cat_title} Emergency"
        suggested_subtitle = f"Support urgent hospital care and treatment in India with 100% verified documentation."
        
        # Breakdown calculation in INR
        primary_cost = round(goal_amount * 0.65, 2)
        secondary_cost = round(goal_amount * 0.25, 2)
        contingency_cost = round(goal_amount - primary_cost - secondary_cost, 2)

        breakdown = [
            {"item": f"Hospitalization, surgery & clinical procedures at hospital", "estimated_amount": primary_cost, "currency": "INR"},
            {"item": "Post-operative medicines, ICU medicines & diagnostic scans", "estimated_amount": secondary_cost, "currency": "INR"},
            {"item": "Emergency patient transport & essential family recovery support", "estimated_amount": contingency_cost, "currency": "INR"}
        ]

        p_str = format_inr(primary_cost)
        s_str = format_inr(secondary_cost)
        c_str = format_inr(contingency_cost)

        structured_story = f"""### The Story

{rough_notes.strip()}

---

### Why We Urgently Need Your Support

A critical {category.lower()} emergency has struck {name}. While we have exhausted personal savings and family loans, the estimated treatment costs at the hospital amount to {formatted_goal}. 

We are raising funds so that money does not stand in the way of saving {name}'s life.

---

### Transparent Fund Utilization (INR)

Every single rupee donated will be directly allocated towards verified treatment expenses:

- **{p_str}**: Direct hospital admission, surgical theater charges, and specialist doctor fees
- **{s_str}**: Prescribed pharmacy medicines, laboratory pathology tests, and supportive care
- **{c_str}**: Post-discharge rehabilitation and emergency family medical buffer

---

### How You Can Help

1. **Donate via UPI / Cards**: Even ₹100, ₹500, or ₹2,000 creates an immediate impact.
2. **Share on WhatsApp & Social Media**: Sharing this verified fundraiser link with your friends and society groups helps us reach kind-hearted donors across India.
3. **Send Prayers & Blessings**: Please keep {name} in your thoughts and prayers for a speedy recovery.

Thank you so much for your generosity and blessing."""

        transparency_tips = [
            "Upload an official signed Hospital Estimate Letter with patient UHID to earn the Verified Trust Shield.",
            "Choose direct Hospital Bank Account settlement so donors know funds go directly to the hospital.",
            "Post clinical milestone updates with doctor notes every 7-10 days."
        ]

        suggested_tags = [category.lower(), "india-medical-aid", "urgent-relief", "verified-fundraiser", "upi-enabled"]

        return StoryEnhanceResponse(
            suggested_title=suggested_title,
            suggested_subtitle=suggested_subtitle,
            structured_story=structured_story,
            recommended_itemized_breakdown=breakdown,
            transparency_tips=transparency_tips,
            suggested_tags=suggested_tags
        )

    async def _enhance_with_gemini(
        self,
        category: str,
        goal_amount: float,
        rough_notes: str,
        beneficiary_name: Optional[str],
        target_audience: Optional[str]
    ) -> Optional[StoryEnhanceResponse]:
        formatted_goal = format_inr(goal_amount)
        prompt = f"""
You are an expert Crowdfunding Campaign Story Strategist specializing in authentic Indian medical and charity fundraisers (like Milaap and Ketto).
Refine the organizer's rough notes into a compelling, transparent, and verified campaign pitch in Indian Rupees (INR).

DETAILS:
- Category: {category}
- Goal Amount: {formatted_goal} (INR)
- Beneficiary: {beneficiary_name or 'Patient'}
- Audience: {target_audience}
- Organizer's Notes:
{rough_notes}

INSTRUCTIONS:
1. Craft an empathetic title and subtitle (non-clickbait, high trust).
2. Structure the story into 4 distinct sections: The Story, Why We Urgently Need Help, Transparent Fund Utilization (INR), and How You Can Support (WhatsApp sharing, UPI).
3. Build a 3-4 item realistic cost breakdown in INR summing to {goal_amount}.
4. Provide 3 specific tips to maximize donor trust in India (e.g. Hospital estimate letter with UHID, direct hospital settlement, 80G tax benefit if applicable).
5. Provide 4 relevant search tags.

Respond ONLY with valid JSON in this format:
{{
  "suggested_title": "string",
  "suggested_subtitle": "string",
  "structured_story": "markdown formatted string",
  "recommended_itemized_breakdown": [
    {{"item": "string", "estimated_amount": float, "currency": "INR"}}
  ],
  "transparency_tips": ["string", "string", "string"],
  "suggested_tags": ["string", "string"]
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return StoryEnhanceResponse(**parsed)
        return None

ai_assistant = AIAssistantService()
