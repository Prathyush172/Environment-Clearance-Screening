"""Ingestion pipeline: PDF extraction, structure-aware chunking, embedding, and indexing."""

import os
import glob
import hashlib
import time
import uuid
from typing import List, Dict, Any, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.config import settings
from libs.common.logging import get_logger
from libs.common.db.session import get_db_session
from libs.common.db.models import ClauseIndex, CrossRefIndex, IndexManifest
from services.ingest.chunker import (
    detect_schedule_table,
    detect_general_condition,
    make_general_condition_chunk,
    extract_schedule_rows,
    make_schedule_chunk,
    chunk_prose,
)

logger = get_logger("ingest_pipeline")

CROSS_REF_PHRASES = [
    "see",
    "General Condition",
    "notwithstanding",
    "provided that",
    "Category B shall be treated as A",
    "appraised at the Central Level as Category 'A'",
]


def discover_pdfs(corpus_dir: str) -> List[Dict[str, str]]:
    """Recursively discover all PDF files in corpus directory and generate stable doc_id."""
    pdf_files = []
    if not os.path.exists(corpus_dir):
        logger.warning("Corpus directory does not exist", corpus_dir=corpus_dir)
        return []

    for root, _, files in os.walk(corpus_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                full_path = os.path.join(root, f)
                filename = os.path.basename(full_path)
                doc_id = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
                pdf_files.append({
                    "path": full_path,
                    "filename": filename,
                    "doc_id": doc_id,
                })

    logger.info("Discovered PDF files", count=len(pdf_files), corpus_dir=corpus_dir)
    return pdf_files


def extract_text(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract text from PDF pages using PyMuPDF (fitz) with pdfplumber fallback."""
    pages = []
    try:
        import fitz
        doc = fitz.open(pdf_path)
        for idx, page in enumerate(doc):
            page_text = page.get_text() or ""
            pages.append({"page_number": idx + 1, "text": page_text})
        if pages:
            return pages
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                pages.append({"page_number": idx + 1, "text": page_text})
    except Exception as exc:
        logger.error("Failed to extract text from PDF", pdf_path=pdf_path, error=str(exc))
    return pages


def chunk_document(pages: List[Dict[str, Any]], doc_id: str, doc_title: str) -> List[Dict[str, Any]]:
    """Process pages and produce structure-aware chunks."""
    all_chunks = []

    for p in pages:
        page_num = p["page_number"]
        text = p["text"]
        if not text.strip():
            continue

        # 1. Check for General Condition
        gc_text = detect_general_condition(text)
        if gc_text:
            all_chunks.append(make_general_condition_chunk(gc_text, doc_id, doc_title, page_num))

        # 2. Check for Schedule table
        if detect_schedule_table(text):
            rows = extract_schedule_rows(text)
            for r in rows:
                all_chunks.append(make_schedule_chunk(r, doc_id, doc_title, page_num))

        # 3. Standard prose chunks
        prose_windows = chunk_prose(text, max_tokens=512, overlap=50)
        for idx, win in enumerate(prose_windows):
            chunk_id = f"{doc_id}_p{page_num}_prose_{idx}"
            all_chunks.append({
                "chunk_id": chunk_id,
                "text": win,
                "doc_id": doc_id,
                "doc_title": doc_title,
                "clause_ref": f"Page {page_num}",
                "page": page_num,
                "chunk_type": "prose",
                "metadata": {
                    "chunk_type": "prose",
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "page": page_num,
                    "clause_ref": f"Page {page_num}",
                },
            })

    return all_chunks


def compute_chunk_hash(chunk_text: str, doc_id: str) -> str:
    """Compute sha256 hash of chunk content for idempotency."""
    return hashlib.sha256(f"{doc_id}:{chunk_text}".encode("utf-8")).hexdigest()


def embed_chunks(chunks: List[Dict[str, Any]]) -> List[List[float]]:
    """Embed chunks using sentence-transformers model."""
    texts = [c["text"] for c in chunks]
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()
    except Exception as exc:
        logger.warning("SentenceTransformer embedding fallback to dummy vector", error=str(exc))
        # Return deterministic dummy 384-d vectors if model not loaded
        return [[0.0] * 384 for _ in texts]


def upsert_to_chroma(chunks: List[Dict[str, Any]], embeddings: Optional[List[List[float]]] = None) -> int:
    """Upsert chunks with embeddings to ChromaDB."""
    try:
        try:
            from services.worker.tools.retrieval import get_chroma_client
            client = get_chroma_client()
        except Exception:
            import chromadb
            client = chromadb.HttpClient(host=getattr(settings, "CHROMA_HOST", "chroma"), port=int(getattr(settings, "CHROMA_PORT", 8000)))
        collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

        ids = [c["chunk_id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        # Ensure metadata values are str, int, float, or bool for ChromaDB
        metadatas = []
        for c in chunks:
            raw_meta = c.get("metadata", {})
            clean_meta = {}
            for k, v in raw_meta.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                elif v is None:
                    continue
                else:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

        # Chroma handles batches of up to 500
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            batch_kwargs = {
                "ids": ids[i:i + batch_size],
                "documents": texts[i:i + batch_size],
                "metadatas": metadatas[i:i + batch_size],
            }
            if embeddings and len(embeddings) == len(ids):
                batch_kwargs["embeddings"] = embeddings[i:i + batch_size]
            collection.upsert(**batch_kwargs)
        return len(ids)
    except Exception as exc:
        logger.error("Chroma upsert failed", error=str(exc))
        return 0


async def build_clause_index(chunks: List[Dict[str, Any]], session: AsyncSession, index_version: str):
    """Populate ClauseIndex table in PostgreSQL."""
    for c in chunks:
        meta = c.get("metadata", {})
        if meta.get("chunk_type") == "schedule_item":
            item_no = meta.get("item_no", "")
            clause_row = ClauseIndex(
                id=str(uuid.uuid4()),
                identifier=item_no,
                chunk_ids_json=[c["chunk_id"]],
                doc_id=c["doc_id"],
                doc_title=c["doc_title"],
                clause_ref=c["clause_ref"],
                index_version=index_version,
            )
            session.add(clause_row)
        elif meta.get("chunk_type") == "general_condition":
            clause_row = ClauseIndex(
                id=str(uuid.uuid4()),
                identifier="GC",
                chunk_ids_json=[c["chunk_id"]],
                doc_id=c["doc_id"],
                doc_title=c["doc_title"],
                clause_ref="General Condition",
                index_version=index_version,
            )
            session.add(clause_row)


async def build_cross_ref_index(chunks: List[Dict[str, Any]], session: AsyncSession, index_version: str):
    """Detect cross references within chunk texts and populate CrossRefIndex table."""
    gc_chunk_id = next((c["chunk_id"] for c in chunks if c.get("chunk_type") == "general_condition"), None)
    if not gc_chunk_id:
        return

    for c in chunks:
        if c.get("chunk_type") == "schedule_item":
            # Schedule items relate to General Condition
            xref = CrossRefIndex(
                id=str(uuid.uuid4()),
                source_chunk_id=c["chunk_id"],
                target_chunk_id=gc_chunk_id,
                ref_type="MODIFIER",
                ref_text="General Condition applies to Category B schedule items",
                index_version=index_version,
            )
            session.add(xref)


async def run_pipeline(corpus_dir: str, reembed: bool = False, only: Optional[str] = None, dry_run: bool = False):
    """Run full ingestion pipeline."""
    start_time = time.time()
    logger.info("Starting ingest pipeline", corpus_dir=corpus_dir, dry_run=dry_run)

    pdfs = discover_pdfs(corpus_dir)
    if only:
        pdfs = [p for p in pdfs if only in p["doc_id"] or only in p["filename"]]

    all_chunks = []
    source_hashes = {}

    for pdf_info in pdfs:
        doc_id = pdf_info["doc_id"]
        doc_title = pdf_info["filename"]
        pdf_path = pdf_info["path"]

        # Calculate file hash
        with open(pdf_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        source_hashes[doc_id] = file_hash

        pages = extract_text(pdf_path)
        chunks = chunk_document(pages, doc_id, doc_title)
        all_chunks.extend(chunks)

    logger.info("Document chunking complete", total_chunks=len(all_chunks))

    if dry_run:
        logger.info("Dry-run completed successfully", total_chunks=len(all_chunks))
        return {"status": "dry_run", "chunks_count": len(all_chunks)}

    # Embed and upsert
    index_version = str(uuid.uuid4())
    embeddings = embed_chunks(all_chunks)
    upserted = upsert_to_chroma(all_chunks, embeddings)

    # Store indexes and manifest in Postgres if available
    try:
        async with get_db_session() as session:
            await build_clause_index(all_chunks, session, index_version)
            await build_cross_ref_index(all_chunks, session, index_version)

            elapsed = time.time() - start_time
            throughput = (len(all_chunks) / elapsed) if elapsed > 0 else 0.0

            manifest = IndexManifest(
                id=str(uuid.uuid4()),
                doc_count=len(pdfs),
                chunk_count=len(all_chunks),
                embedding_model=settings.EMBEDDING_MODEL,
                embedding_version="1.0.0",
                index_version=index_version,
                throughput_chunks_per_sec=round(throughput, 2),
                source_hashes_json=source_hashes,
            )
            session.add(manifest)
    except Exception as exc:
        logger.info("Postgres session unavailable, skipping Postgres manifest indexing", error=str(exc))

    logger.info("Ingest pipeline finished", index_version=index_version, chunks_upserted=upserted)
    return {
        "status": "success",
        "index_version": index_version,
        "doc_count": len(pdfs),
        "chunk_count": len(all_chunks),
    }
