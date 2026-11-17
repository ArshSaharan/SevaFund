"""Production document retrieval, reproduced exactly on its no-embedding path, with no API call.

`app.services.rag.retrieve_evidence` is called unchanged.  For the duration of one call:
  * each authored document is written as a UTF-8 .txt "upload" in a private temporary directory, and rag's upload
    directory points there (production extracts .txt uploads verbatim);
  * rag sees a copy of the settings with no API key, so production takes its own lexical fallback;
  * rag's HTTP helper is replaced by a guard that records and refuses any request (it must stay unused).
Everything is restored afterwards.  The query and location strings use the production formats.
Differences from production's primary path are recorded in the pre-registration (embedding ranking is not used).
"""
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple


def production_location(data: dict) -> str:
    """app/routers/campaigns.py; country defaults to the CampaignCreate schema default 'IN'."""
    return f"{data.get('city') or ''}, {data.get('state') or ''} {data.get('country') or 'IN'}".strip(", ")


def production_query(data: dict) -> str:
    """app/services/ai_verifier.py evidence_query."""
    from app.services.fraud_detector import format_inr
    return (f"{data['title']} {data['category']} {data.get('beneficiary_name') or ''} {production_location(data) or ''} "
            f"{data['story']} {format_inr(data['goal_amount'])}")


@contextmanager
def _isolated_rag(directory: Path):
    from app.config import settings
    from app.services import rag
    saved = (rag.UPLOAD_DIR, rag.settings, rag.post_json)
    attempted: List[str] = []

    async def refuse(url, *args, **kwargs):
        attempted.append(str(url).split("?")[0].rsplit("/", 1)[-1])
        raise RuntimeError("network access is disabled during evaluation retrieval")

    rag.UPLOAD_DIR = directory
    rag.settings = settings.model_copy(update={"GEMINI_API_KEY": ""})
    rag.post_json = refuse
    try:
        yield attempted
    finally:
        rag.UPLOAD_DIR, rag.settings, rag.post_json = saved


async def retrieve(data: dict, top_k: int = 5) -> Tuple[List[dict], dict]:
    """Chunks exactly as production's retrieve_evidence returns them without embeddings, plus coverage facts."""
    from app.services import rag
    with tempfile.TemporaryDirectory(prefix="sevafund_v5_retrieval_") as tmp:
        directory = Path(tmp).resolve()
        documents = []
        for index, document in enumerate(data.get("documents", [])):
            name = f"doc{index:03d}.txt"
            (directory / name).write_text(document.get("content", ""), encoding="utf-8")
            documents.append({"title": document.get("title"), "doc_type": document.get("doc_type", "OTHER"),
                              "file_url": f"/uploads/{name}"})
        with _isolated_rag(directory) as attempted:
            chunks = await rag.retrieve_evidence(documents, production_query(data), top_k=top_k)
        total = sum(len(rag.chunk_document(d.get("content", ""), {"title": d.get("title")}))
                    for d in data.get("documents", []))
    if attempted:
        raise RuntimeError(f"retrieval attempted {len(attempted)} network request(s); refusing to continue")
    for chunk in chunks:
        chunk["file_url"] = None
    return chunks, {"total_chunks": min(total, rag.MAX_CHUNKS), "retrieved": len(chunks),
                    "all_chunks_retrieved": len(chunks) == min(total, rag.MAX_CHUNKS),
                    "embedding_requests": 0, "mode": "production_no_embedding_fallback"}
