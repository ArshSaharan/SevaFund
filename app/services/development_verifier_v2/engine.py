"""Development-only v2 verification pipeline.  Never wired into production.

    extraction -> normalization -> consistency -> category -> semantic
               -> (optional external reasoners) -> scoring/decision -> audit

Each stage runs in its own guard.  A failing stage is recorded as an error and
the case can then only end as FLAG_FOR_REVIEW (if a material contradiction was
already found) or VERIFICATION_ERROR - never APPROVED.
"""
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .audit import AuditTrail
from .category import COST, positive_signals, profile_for
from .config import DEFAULT_CONFIG, ENGINE_VERSION, VerifierConfig
from .consistency import CHECKS, Context
from .decision import decide
from .extraction import extract_claim, extract_document
from .schemas import CaseInput, Decision, DocumentInput, Finding, Requirement, Severity, VerificationDecision
from .semantic import SIGNALS

# An external reasoner (e.g. a future Gemini cross-check) receives the context
# and returns findings.  None are registered by default and the offline
# evaluation never calls one; any such component must be evaluated separately.
Reasoner = Callable[[Context], List[Finding]]


def verify_case(case: CaseInput, config: VerifierConfig = DEFAULT_CONFIG,
                reasoners: Sequence[Reasoner] = ()) -> VerificationDecision:
    audit = AuditTrail(case, ENGINE_VERSION, config.digest())
    errors: List[str] = []
    findings: List[Finding] = []
    requirements = []
    evidence = []
    signals: List[str] = []

    try:
        claim = extract_claim(case)
        evidence = [extract_document(i, d) for i, d in enumerate(case.documents)]
        audit.stage("extraction", documents=len(evidence), readable=sum(e.readable for e in evidence),
                    fields=sum(len(e.fields) for e in evidence))
    except Exception as exc:          # noqa: BLE001 - any failure must block approval
        errors.append(audit.error("extraction", exc))
        claim = None

    for doc in evidence:
        for issue in doc.issues:
            if issue.startswith("LOAD_ERROR"):
                errors.append(f"Document '{doc.title}' could not be retrieved or extracted ({issue.split(':', 1)[1]}).")

    unreadable = [doc for doc in evidence if not doc.readable and not any(i.startswith("LOAD_ERROR") for i in doc.issues)]
    readable = [doc for doc in evidence if doc.readable]
    texts: Dict[int, str] = {i: (d.text or "") for i, d in enumerate(case.documents)}

    if claim is not None:
        profile = profile_for(case.category)
        ctx = Context(case=case, claim=claim, docs=readable, texts=texts, config=config,
                      concepts=profile.concepts if config.enable_category else {})
        stages = []
        if config.enable_cross_document:
            stages += [(f"consistency.{check.__name__}", check) for check in CHECKS]
        if config.enable_semantic:
            stages += [(f"semantic.{signal.__name__}", signal) for signal in SIGNALS]
        stages += [(f"reasoner.{getattr(r, '__name__', 'external')}", r) for r in reasoners]
        for name, stage in stages:
            try:
                produced = stage(ctx)
                findings.extend(produced)
                audit.stage(name, findings=len(produced))
            except Exception as exc:  # noqa: BLE001
                errors.append(audit.error(name, exc))
        try:
            if config.enable_category:
                requirements = profile.requirements(ctx)
            else:
                # Without category awareness only generic cost evidence is required.
                found = COST.check(ctx)
                requirements = [Requirement(key=COST.key, description=COST.description, satisfied=bool(found),
                                            satisfied_by=found, request="" if found else COST.request)]
            signals = positive_signals(ctx, requirements)
            audit.stage("category", profile=profile.name, requirements=len(requirements),
                        unmet=sum(not r.satisfied for r in requirements))
        except Exception as exc:      # noqa: BLE001
            errors.append(audit.error("category", exc))

    if unreadable:
        findings.append(Finding(
            kind="document_quality", code="UNREADABLE_DOCUMENT", dimension="documentation", component="extraction",
            severity=Severity.UNCERTAIN, confidence=0.5,
            summary=f"{len(unreadable)} document(s) could not be read.",
            explanation="An unreadable upload cannot support or contradict the campaign; a legible copy is needed."))

    result = decide(findings, requirements, errors, config, document_count=len(readable))
    result.evidence = evidence
    result.positive_signals = signals if result.decision != Decision.VERIFICATION_ERROR else []
    result.engine_version = ENGINE_VERSION
    reason_codes = ([f"DECISION_{result.decision.value}"] + [f.code for f in findings]
                    + [f"UNMET_{r.key.upper()}" for r in requirements if not r.satisfied]
                    + (["STAGE_ERROR"] if errors else []))
    result.audit = audit.finish(result.decision.value, list(dict.fromkeys(reason_codes)),
                                result.influencing_dimensions, findings)
    return result


def load_documents(references: Iterable[Dict], upload_dir: Path,
                   extractor: Optional[Callable[[Path], str]] = None) -> List[DocumentInput]:
    """Stage 1 for uploaded files: resolve each reference inside ``upload_dir``
    and extract its text with the production extractor (``rag.extract_document_text``).

    Failures become ``load_error`` categories instead of exceptions, so a
    missing file or a broken PDF is visible to the decision stage.
    """
    if extractor is None:
        from app.services.rag import extract_document_text as extractor
    root = upload_dir.resolve()
    documents = []
    for reference in references:
        title = reference.get("title") or "Supporting document"
        doc_type = reference.get("doc_type", "OTHER")
        name = Path(str(reference.get("file_url", "")).split("?", 1)[0]).name
        path = (root / name).resolve()
        if not name or path.parent != root or not path.is_file():
            documents.append(DocumentInput(title=title, doc_type=doc_type, load_error="FILE_NOT_FOUND"))
            continue
        try:
            text = extractor(path)
        except Exception as exc:      # noqa: BLE001
            documents.append(DocumentInput(title=title, doc_type=doc_type,
                                           load_error=f"EXTRACTION_FAILED_{type(exc).__name__}"))
            continue
        documents.append(DocumentInput(title=title, doc_type=doc_type, text=text,
                                       file_url=reference.get("file_url")))
    return documents
