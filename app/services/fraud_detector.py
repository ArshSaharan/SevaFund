import re
from typing import Dict, Any, List, Optional, Tuple

# Comprehensive Indian Cost Benchmark Table (in INR - ₹)
# Based on average treatment and out-of-pocket costs across private & government hospitals in India (AIIMS, Tata Memorial, Apollo, Fortis, etc.)
INDIAN_COST_BENCHMARKS = {
    # Medical & Oncology in India
    "cancer": {"min": 300000, "max": 2500000, "avg": 1000000, "label": "Cancer Oncology, Chemotherapy & Radiation Therapy in India"},
    "chemotherapy": {"min": 150000, "max": 1200000, "avg": 500000, "label": "Chemotherapy & Targeted Immunotherapy Cycles"},
    "heart surgery": {"min": 180000, "max": 800000, "avg": 350000, "label": "Open Heart Bypass (CABG) / Valve Replacement"},
    "organ transplant": {"min": 1500000, "max": 4500000, "avg": 2600000, "label": "Liver / Kidney / Bone Marrow Transplant"},
    "kidney transplant": {"min": 800000, "max": 2500000, "avg": 1400000, "label": "Kidney Transplant & Immunosuppressant Therapy"},
    "icu": {"min": 100000, "max": 1200000, "avg": 400000, "label": "Extended ICU Critical Care & Ventilator Support"},
    "broken bone": {"min": 25000, "max": 250000, "avg": 85000, "label": "Orthopedic Fracture Surgery & Implants"},
    "surgery": {"min": 35000, "max": 500000, "avg": 150000, "label": "General Surgical Procedure in India"},
    "appendectomy": {"min": 25000, "max": 140000, "avg": 60000, "label": "Laparoscopic Appendectomy Surgery"},
    "nicu": {"min": 150000, "max": 1200000, "avg": 450000, "label": "Neonatal Intensive Care (NICU) Infant Support"},
    "dialysis": {"min": 30000, "max": 300000, "avg": 120000, "label": "Renal Dialysis Annual Regimen"},
    
    # Funeral & Memorial in India
    "funeral": {"min": 10000, "max": 100000, "avg": 35000, "label": "Antyesti / Cremation / Memorial Rites in India"},
    "cremation": {"min": 8000, "max": 60000, "avg": 25000, "label": "Cremation and Post-Death Ceremonies"},
    "memorial": {"min": 15000, "max": 150000, "avg": 50000, "label": "Memorial and Family Support"},

    # Emergency & Natural Disasters in India
    "flood": {"min": 25000, "max": 500000, "avg": 150000, "label": "Flood Relief & Essential Household Rehabilitation"},
    "fire": {"min": 50000, "max": 800000, "avg": 250000, "label": "House Fire Reconstruction & Living Essentials"},
    "accident": {"min": 30000, "max": 600000, "avg": 180000, "label": "Emergency Trauma / Road Accident Medical Care"},

    # Education in India
    "tuition": {"min": 30000, "max": 800000, "avg": 200000, "label": "College / University Annual Tuition Fee in India"},
    "semester": {"min": 20000, "max": 400000, "avg": 100000, "label": "Single College Semester Fee"},
    "school fee": {"min": 10000, "max": 150000, "avg": 45000, "label": "School Education & Books Assistance"},

    # Animals / Veterinary in India
    "vet": {"min": 3000, "max": 60000, "avg": 18000, "label": "Veterinary Surgery & Pet Medical Treatment"},
    "dog surgery": {"min": 5000, "max": 50000, "avg": 15000, "label": "Canine Emergency Surgical Care"},
}

# Indian Red Flag Indicators
RED_FLAG_PATTERNS = [
    (r"\b(send to my personal upi|paytm karo direct|gpay to personal number|send directly to my account)\b", "Solicits direct unmonitored personal UPI/GPay transfers bypassing platform trust escrow", 35),
    (r"\b(western union|hawala|moneygram|crypto|bitcoin|gift card)\b", "Requests untraceable or illegal payment channels", 40),
    (r"\b(100% guarantee cancer cure|ayurvedic miracle cure for cancer|secret babaji remedy|cured in 3 days without doctor)\b", "Claims unverified miracle cures or fraudulent medical treatments", 35),
    (r"\b(lottery|kaun banega crorepati prize|kbc lottery|won prize money|claim reward)\b", "Classic Indian advance-fee/lottery scam keywords", 50),
    (r"\b(fake bill|photoshop receipt|fake aiims stamp|edited hospital letter)\b", "Mention of fraudulent documentation or stamp forgery", 50),
    (r"\b(send money urgent right this second or die|no questions allowed)\b", "High-pressure coercive emotional blackmail without verifiable clinical records", 20),
    (r"\b(buy me iphone|luxury trip|party expenses)\b", "Frivolous luxury claims disguised as hardship", 30),
]

# Indian Specificity Indicators (Hospitals, Institutions, Doctors, Indian Locations)
INDIAN_SPECIFICITY_PATTERNS = [
    (r"\b(AIIMS|Tata Memorial|Apollo|Fortis|Max Healthcare|Manipal|Narayana Health|CMC Vellore|Medanta|PGIMER|Sir Ganga Ram|Kokilaben|KEM Hospital|Safdarjung|Christian Medical College|SGPGI|Hinduja|Lilavati)\b", "Names a recognized premier Indian hospital / healthcare network"),
    (r"\b(hospital|clinic|nursing home|medical college|trauma center|dispensary|chc|phc)\b", "Cites a healthcare institution or clinic"),
    (r"\b(dr\.|doctor|surgeon|physician|oncologist|cardiologist|consultant)\b", "Names an attending doctor or specialist"),
    (r"\b(estimate letter|hospital quotation|discharge summary|opd card|uhid|admission slip|ayushman bharat|pmjay|bpl card)\b", "Cites authentic Indian medical billing / admission records (UHID/Estimate)"),
    (r"\b(diagnosis|diagnosed|biopsy|mri|ct scan|dialysis|chemo|chemotherapy|radiation|ecg|blood test)\b", "Contains verified clinical diagnostic terminology"),
    (r"\b([₹Rs\.]+\s?[\d,]+(\s?lakh|\s?crore|\s?k)?)\b", "Provides itemized cost figures in Indian Rupee denomination"),
    (r"\b(Delhi|Mumbai|Bengaluru|Bangalore|Hyderabad|Chennai|Kolkata|Pune|Ahmedabad|Jaipur|Lucknow|Chandigarh|Kochi|Kerala|Punjab|Maharashtra|Karnataka|Tamil Nadu|Gujarat|UP|Bihar|Haryana|Rajasthan|West Bengal|Assam|Odisha)\b", "Specifies identifiable Indian city / state geography"),
]

def format_inr(amount: float) -> str:
    """Formats a number in Indian Lakhs/Crores/Rupees notation (e.g. ₹12,50,000)"""
    s = f"{int(amount)}"
    if len(s) <= 3:
        return f"₹{amount:,.2f}"
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    formatted = ",".join(parts) + "," + last3
    return f"₹{formatted}"

def analyze_cost_benchmark(category: str, text: str, goal_amount: float) -> Optional[Dict[str, Any]]:
    """
    Compares the requested INR goal against known Indian medical, disaster, and education benchmarks.
    """
    text_lower = text.lower()
    matched_key = None
    
    for key in INDIAN_COST_BENCHMARKS:
        if key in text_lower:
            matched_key = key
            break
            
    if not matched_key:
        cat_lower = category.lower()
        if "medical" in cat_lower:
            matched_key = "surgery"
        elif "memorial" in cat_lower or "funeral" in cat_lower:
            matched_key = "funeral"
        elif "education" in cat_lower:
            matched_key = "tuition"
        elif "animal" in cat_lower:
            matched_key = "vet"
        elif "emergency" in cat_lower:
            matched_key = "accident"
            
    if not matched_key or matched_key not in INDIAN_COST_BENCHMARKS:
        return None
        
    bench = INDIAN_COST_BENCHMARKS[matched_key]
    ratio = goal_amount / bench["avg"] if bench["avg"] > 0 else 1.0
    
    formatted_goal = format_inr(goal_amount)
    formatted_min = format_inr(bench["min"])
    formatted_max = format_inr(bench["max"])

    if goal_amount > (bench["max"] * 1.75):
        status = "SUSPICIOUSLY_EXCESSIVE"
        insight = (f"The requested {formatted_goal} is {ratio:.1f}x higher than standard Indian hospital costs "
                   f"({formatted_min} - {formatted_max}) for {bench['label']}. Requires official signed hospital estimate letter.")
    elif goal_amount > bench["max"]:
        status = "SLIGHTLY_ELEVATED"
        insight = (f"The requested {formatted_goal} is higher than typical Indian average ({formatted_min} - {formatted_max}). "
                   f"Acceptable for multi-stage ICU or tertiary super-specialty hospitals, but doctor estimate letter is mandatory.")
    else:
        status = "WITHIN_NORMAL_RANGE"
        insight = f"The requested {formatted_goal} aligns with typical Indian healthcare benchmarks ({formatted_min} - {formatted_max})."
        
    return {
        "category": category,
        "item_detected": bench["label"],
        "requested_amount": goal_amount,
        "typical_range_min": bench["min"],
        "typical_range_max": bench["max"],
        "ratio_to_benchmark": round(ratio, 2),
        "benchmark_status": status,
        "insight": insight
    }

def detect_red_flags(text: str) -> Tuple[List[str], float]:
    """
    Scans campaign text for Indian fraud patterns, personal UPI requests, fake promises.
    """
    text_lower = text.lower()
    flags = []
    penalty = 0.0
    
    for pattern, description, score_penalty in RED_FLAG_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            flags.append(description)
            penalty += score_penalty

    # Compound penalty if multiple scam markers are present
    if len(flags) >= 2:
        penalty += 20.0
            
    # Check for short or empty text
    if len(text.strip().split()) < 25:
        flags.append("Story is unusually brief (under 25 words); lacks necessary medical context")
        penalty += 25
        
    # Check for excessive uppercase
    letters = [c for c in text if c.isalpha()]
    if letters and (sum(1 for c in letters if c.isupper()) / len(letters)) > 0.6:
        flags.append("Excessive uppercase lettering indicates aggressive urgency pattern")
        penalty += 15

    return flags, min(penalty, 100.0)

def extract_specificity_signals(text: str, location: Optional[str] = None) -> Tuple[List[str], float]:
    """
    Evaluates evidence density and factual specificity in Indian context.
    """
    signals = []
    raw_score = 20.0
    
    for pattern, desc in INDIAN_SPECIFICITY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            signals.append(desc)
            raw_score += 15.0
            
    word_count = len(text.split())
    if word_count > 150:
        signals.append("Comprehensive narrative provided (over 150 words)")
        raw_score += 15.0
    elif word_count > 75:
        signals.append("Adequate narrative length")
        raw_score += 10.0
        
    if location and len(location.strip()) > 3:
        signals.append(f"Geographic location specified ({location.strip()})")
        raw_score += 10.0

    return signals, min(raw_score, 100.0)
