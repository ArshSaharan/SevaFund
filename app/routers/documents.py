import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from app.models.user import User
from app.services.auth_dependencies import get_current_user

from app.services.rag import UPLOAD_DIR

router = APIRouter(prefix="/documents", tags=["Supporting documents"])
ALLOWED_TYPES = {"application/pdf": ".pdf", "text/plain": ".txt", "text/markdown": ".md"}
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("OTHER"),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Store a beneficiary proof file for campaign-scoped retrieval."""
    suffix = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()
    if suffix not in {".pdf", ".txt", ".md"} or content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a PDF, TXT, or Markdown document")
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content or len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Document must be between 1 byte and 20 MB")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(415, "The uploaded file is not a valid PDF")
    if suffix in {".txt", ".md"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, "Text documents must use UTF-8 encoding") from exc

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    (UPLOAD_DIR / stored_name).write_bytes(content)
    return {
        "doc_type": doc_type.upper(),
        "title": title or Path(file.filename or "Supporting document").stem,
        "file_url": f"/private-documents/{stored_name}",
        "verified": False,
    }
