"""Stage 4: category-aware verification behind one shared interface.

Every category profile declares (a) the evidence a reviewer needs before a
campaign can be approved and (b) a small concept lexicon used to decide whether
two descriptions of a treatment / course / work refer to the same thing.

Unsatisfied requirements produce *information requests*, never fraud
findings: missing evidence is not proof of fraud.  Education and community
campaigns are never asked for medical evidence.
"""
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Set

from .consistency import Context, claimed_institutions, stem
from .normalize import MATCH, compare_names, compare_orgs
from .schemas import DocumentEvidence, Requirement

# An itemised row: some words, then an amount closing the line (any column spacing).
_TABLE_ROW = re.compile(r"^[ \t]*(?=[^\n]*[A-Za-z])[^\n]*?(?:[ \t]|:|\.{2,})(?:rs\.?[ \t]*|₹[ \t]*|inr[ \t]*)?"
                        r"\d[\d,]*(?:\.\d+)?(?:/-)?[ \t]*$", re.I | re.M)


def _lexicon(groups: Dict[str, str]) -> Dict[str, Set[str]]:
    return {name: {stem(word) for word in words.split()} for name, words in groups.items()}


MEDICAL_CONCEPTS = _lexicon({
    "renal": "kidney kidneys renal nephrology nephrologist dialysis haemodialysis hemodialysis transplant",
    "neonatal": "nicu neonatal neonate newborn preterm premature prematurity incubator infant",
    "spine": "spine spinal lumbar disc slipped vertebra vertebral tlif fusion sciatica",
    "joint": "knee hip joint arthroplasty",
    "oncology": "cancer oncology oncologist chemotherapy chemo leukaemia leukemia lymphoblastic tumour tumor "
                "haemato hemato radiotherapy lymphoma",
    "trauma": "fracture fractured femur bone rod fixation orthopaedic orthopedic accident trauma thigh",
    "eye": "eye eyes cataract retina retinal vision ophthalmic ophthalmology",
    "abdominal": "gall bladder gallbladder hernia appendix appendectomy cholecystectomy",
    "cardiac": "heart cardiac bypass valve angioplasty",
})
EDUCATION_CONCEPTS = _lexicon({
    "engineering": "engineering btech civil mechanical electrical polytechnic",
    "nursing": "nursing nurse gnm midwifery anm",
    "schooling": "school schooling pupil",
    "public_health": "msc public health epidemiology",
    "civil_services": "upsc civil services ias coaching foundation",
    "hospitality": "hotel hospitality catering fashion design",
    "computing": "computer computing software programming",
    "language": "english spoken language",
})
COMMUNITY_CONCEPTS = _lexicon({
    "water": "borewell bore well hand pump drinking water tank",
    "sanitation": "toilet toilets latrine sanitation washroom",
    "relief": "relief ration rations kits flood tarpaulin grain",
    "livelihood": "sewing tailoring stitch overlock machines",
    "library": "library books reading racks",
    "entertainment": "sound stage lighting banquet catering guests",
    "sports": "cricket sports jerseys kits",
    "decoration": "painting paint boundary gate whitewash",
    "vehicle": "autorickshaw rickshaw vehicle",
    "lighting": "light lights lighting lamp lamps solar streetlight streetlights",
})


@dataclass
class RequirementSpec:
    key: str
    description: str
    request: str
    check: Callable[[Context], List[str]]    # returns titles of satisfying documents


def _traceable_cost(ctx: Context) -> List[str]:
    return [d.title for d in ctx.docs if "cost" in d.evidence_classes
            and d.traceability >= ctx.config.min_traceability]


def _with_class(name: str) -> Callable[[Context], List[str]]:
    return lambda ctx: [d.title for d in ctx.docs if name in d.evidence_classes]


def _subject_identity(ctx: Context) -> List[str]:
    name = ctx.case.beneficiary_name
    if not name:
        return []
    return [d.title for d in ctx.docs
            if any(compare_names(name, f.value)[0] == MATCH for f in d.of("person", "subject"))]


def _organisation_named(ctx: Context) -> List[str]:
    claimed = claimed_institutions(ctx)
    if not claimed:
        return []
    hits = []
    for doc in ctx.docs:
        names = ([doc.issuer] if doc.issuer else []) + [f.value for f in doc.of("organisation")]
        if any(compare_orgs(c, n)[0] == MATCH for c in claimed for n in names):
            hits.append(doc.title)
    return hits


def _itemised(ctx: Context) -> List[str]:
    return [d.title for d in ctx.docs if "cost" in d.evidence_classes
            and len(_TABLE_ROW.findall(ctx.texts.get(d.index, ""))) >= 2]


COST = RequirementSpec("cost_evidence", "A dated, attributable cost document (estimate, bill, fee demand or quotation).",
                       "Upload the cost document on the issuer's letterhead showing the date, a reference number "
                       "and the itemised amount.", _traceable_cost)
IDENTITY = RequirementSpec("beneficiary_identity", "A document that names the beneficiary as stated in the campaign.",
                           "Upload a document issued by the institution that names the beneficiary.", _subject_identity)
INSTITUTION = RequirementSpec("institution_named", "A document from or about the institution the campaign names.",
                              "Upload a document issued by, or addressed to, the institution named in the campaign.",
                              _organisation_named)


@dataclass
class CategoryProfile:
    name: str
    concepts: Dict[str, Set[str]]
    individual: List[RequirementSpec]
    organisation: List[RequirementSpec]

    def requirements(self, ctx: Context) -> List[Requirement]:
        specs = self.organisation if ctx.is_organisation else self.individual
        result = []
        for spec in specs:
            if spec is INSTITUTION and not claimed_institutions(ctx):
                continue        # nothing to confirm if the campaign names no institution
            satisfied_by = spec.check(ctx)
            result.append(Requirement(key=spec.key, description=spec.description, satisfied=bool(satisfied_by),
                                      satisfied_by=satisfied_by, request="" if satisfied_by else spec.request))
        return result


MEDICAL = CategoryProfile(
    "MEDICAL", MEDICAL_CONCEPTS,
    individual=[COST,
                RequirementSpec("clinical_record", "A clinical record: diagnosis, admission or discharge record, or "
                                "the treating doctor's letter.", "Upload a clinical document from the treating "
                                "hospital (diagnosis, admission record, discharge summary or doctor's letter).",
                                _with_class("clinical")),
                IDENTITY, INSTITUTION],
    organisation=[COST, INSTITUTION],
)
EDUCATION = CategoryProfile(
    "EDUCATION", EDUCATION_CONCEPTS,
    individual=[COST,
                RequirementSpec("enrolment_proof", "Proof of enrolment or admission: bonafide certificate, admission "
                                "or offer letter, or enrolment confirmation.", "Upload a bonafide certificate, "
                                "admission/offer letter or enrolment confirmation from the institution.",
                                _with_class("enrollment")),
                IDENTITY, INSTITUTION],
    organisation=[COST, INSTITUTION],
)
COMMUNITY = CategoryProfile(
    "COMMUNITY", COMMUNITY_CONCEPTS,
    individual=[COST, RequirementSpec("itemised_budget", "An itemised budget for the work.",
                                      "Upload a quotation or budget that itemises the costs.", _itemised)],
    organisation=[COST,
                  RequirementSpec("organisation_identity", "Registration or recognition of the organisation "
                                  "(registration certificate or a record citing its registration number).",
                                  "Upload the organisation's registration certificate or a recognition letter "
                                  "citing its registration number.", _with_class("org_identity")),
                  RequirementSpec("itemised_budget", "An itemised budget for the work.",
                                  "Upload a quotation or budget that itemises the costs.", _itemised),
                  INSTITUTION],
)
GENERIC = CategoryProfile("OTHER", {}, individual=[COST, IDENTITY], organisation=[COST, INSTITUTION])
PROFILES = {"MEDICAL": MEDICAL, "EDUCATION": EDUCATION, "COMMUNITY": COMMUNITY}


def profile_for(category: str) -> CategoryProfile:
    upper = (category or "").upper()
    for key, profile in PROFILES.items():
        if key[:4] in upper:
            return profile
    if any(word in upper for word in ("SOCIAL", "NGO", "EMERGENCY", "DISASTER")):
        return COMMUNITY
    return GENERIC


def positive_signals(ctx: Context, requirements: List[Requirement]) -> List[str]:
    signals = [f"{r.description.rstrip('.')} - provided ({', '.join(r.satisfied_by)})."
               for r in requirements if r.satisfied]
    staff = {f.value for d in ctx.docs for f in d.of("person", "staff")}
    if staff and profile_for(ctx.case.category) is MEDICAL:
        signals.append("A treating doctor is named in the documents.")
    if any("authorization" in d.evidence_classes for d in ctx.docs):
        signals.append("A resolution, sanction or work order authorises the work.")
    if any("beneficiary_info" in d.evidence_classes for d in ctx.docs):
        signals.append("Intended beneficiaries are described in the documents.")
    return signals
