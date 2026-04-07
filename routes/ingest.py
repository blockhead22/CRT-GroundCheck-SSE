"""File ingestion route — accepts a local file path, reads content, stores as CRT memory."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field

from routes.deps import sanitize_thread_id, resolve_user_id
from personal_agent.crt_memory import detect_injection_risk

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class FileIngestRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to ingest")
    thread_id: str = Field(default="default")


class FileIngestResponse(BaseModel):
    success: bool
    filename: str
    chars_ingested: int
    memory_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".py", ".js", ".ts", ".csv", ".log", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".html", ".xml", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 3000  # characters per memory chunk (keeps embeddings focused)


def _read_text_file(path: Path) -> str:
    """Read a text file with common encoding fallbacks."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError(f"Could not decode {path.name} with any supported encoding")


def _read_pdf_file(path: Path) -> str:
    """Best-effort PDF text extraction."""
    # Try PyPDF2 first
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
    except ImportError:
        pass

    # Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n\n".join(pages)
    except ImportError:
        pass

    # Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(str(path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        pass

    raise ImportError(
        "No PDF library available. Install one of: PyPDF2, pdfplumber, or PyMuPDF (pip install PyPDF2)"
    )


def _chunk_text(text: str, filename: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks, prefixed with filename context."""
    text = text.strip()
    if not text:
        return []

    # If small enough, single chunk
    if len(text) <= chunk_size:
        return [f"[File: {filename}]\n{text}"]

    chunks = []
    # Split on double-newlines (paragraphs) first, fall back to hard split
    paragraphs = text.split("\n\n")
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    # Hard-split any remaining oversized chunks
    final = []
    for chunk in chunks:
        while len(chunk) > chunk_size:
            final.append(chunk[:chunk_size])
            chunk = chunk[chunk_size:]
        if chunk:
            final.append(chunk)

    return [f"[File: {filename}] (part {i+1}/{len(final)})\n{c}" for i, c in enumerate(final)]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def _get_engine(request: Request, thread_id: str):
    return request.app.state.get_engine(thread_id)


@router.post("/api/ingest/file", response_model=FileIngestResponse)
def ingest_file(req: FileIngestRequest, request: Request, authorization: Optional[str] = Header(None)):
    """Ingest a local file into CRT memory."""
    tid = sanitize_thread_id(req.thread_id)
    uid = resolve_user_id(authorization)

    file_path = Path(req.file_path)

    # Validate
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {req.file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    size = file_path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large: {size / 1024 / 1024:.1f} MB (max {MAX_FILE_SIZE / 1024 / 1024:.0f} MB)")

    # Read content
    try:
        if ext == ".pdf":
            content = _read_pdf_file(file_path)
        elif ext == ".json":
            raw = _read_text_file(file_path)
            # Pretty-print JSON for better memory storage
            try:
                parsed = json.loads(raw)
                content = json.dumps(parsed, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                content = raw
        else:
            content = _read_text_file(file_path)
    except ImportError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    # Chunk and store
    chunks = _chunk_text(content, file_path.name)
    engine = _get_engine(request, tid)

    from personal_agent.crt_rag import MemorySource

    stored_count = 0
    injection_count = 0
    for chunk in chunks:
        # Scan chunk for prompt-injection patterns before storage.
        # Flagged chunks get reduced confidence so they can't dominate retrieval.
        chunk_confidence = 0.90
        if detect_injection_risk(chunk):
            chunk_confidence = 0.35  # well below normal — flagged content
            injection_count += 1
            logger.warning(
                "[INGEST][INJECTION_DEFENSE] Channel=file_ingest, flagged chunk from %s: %.120s",
                file_path.name, chunk,
            )
        try:
            engine.ingest_memory_write(
                text=chunk,
                confidence=chunk_confidence,
                source=MemorySource.USER,
                context={"thread_id": tid, "ingested_from": file_path.name},
                user_marked_important=False,
                contradiction_signal=0.0,
                thread_id=tid,
                authority="provisional" if chunk_confidence < 0.90 else "confirmed",
                channel="file_ingest",
                origin=f"file:{file_path.name}",
                kind="observation",
                source_kind="principal",
                model_id=None,
                run_id=None,
                user_id=uid,
            )
            stored_count += 1
        except Exception as e:
            logger.error(f"[INGEST] Failed to store chunk {stored_count + 1} from {file_path.name}: {e}")

    if injection_count:
        logger.warning(
            "[INGEST] %d/%d chunks from %s flagged for injection risk",
            injection_count, len(chunks), file_path.name,
        )

    logger.info(f"[INGEST] Ingested {file_path.name}: {len(content)} chars, {stored_count}/{len(chunks)} chunks stored")

    return FileIngestResponse(
        success=stored_count > 0,
        filename=file_path.name,
        chars_ingested=len(content),
        memory_count=stored_count,
        error=None if stored_count == len(chunks) else f"Only {stored_count}/{len(chunks)} chunks stored",
    )
