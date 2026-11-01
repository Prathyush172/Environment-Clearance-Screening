"""Corpus retrieval tools for querying ChromaDB and Schedule clauses."""

import os
import asyncio
from typing import List, Dict, Any, Optional

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
try:
    import posthog
    posthog.capture = lambda *args, **kwargs: None
except Exception:
    pass

from libs.common.config import settings
from libs.common.logging import get_logger
from libs.common.corpus_constants import (
    GENERAL_CONDITION_VERBATIM,
    GC_PRIMARY_DISTANCE_KM,
    GC_ENHANCED_DISTANCE_KM,
    GC_ENHANCED_THRESHOLD_ITEMS,
)

logger = get_logger("retrieval_tool")


def get_chroma_client():
    """Retrieve connected ChromaDB client using configured endpoints or local persistence."""
    import chromadb

    # 1. Check if direct CHROMA_URL is specified
    if getattr(settings, "CHROMA_URL", None):
        try:
            client = chromadb.HttpClient(settings.CHROMA_URL)
            client.heartbeat()
            return client
        except Exception:
            pass

    # 2. Prioritize local persistent directory if it exists and contains index
    persist_dir = getattr(settings, "CHROMA_PERSIST_DIRECTORY", "./data/chroma")
    if os.path.exists(persist_dir):
        try:
            return chromadb.PersistentClient(path=persist_dir)
        except Exception:
            pass

    # 3. Try configured CHROMA_HOST:CHROMA_PORT (works inside Docker network)
    chroma_host = getattr(settings, "CHROMA_HOST", "chroma")
    chroma_port = getattr(settings, "CHROMA_PORT", 8000)
    if chroma_host not in ("localhost", "127.0.0.1"):
        try:
            import socket
            socket.getaddrinfo(chroma_host, chroma_port, proto=socket.IPPROTO_TCP)
            client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            client.heartbeat()
            return client
        except Exception:
            pass

    # 4. Fallback to local persistent ChromaDB storage
    os.makedirs(persist_dir, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


async def corpus_search(query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search EIA corpus in ChromaDB by semantic similarity.

    Returns:
        List of {chunk_id, text, score, doc_id, doc_title, clause_ref, metadata}
    """
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)

        if collection.count() > 0:
            def _query_sync():
                return collection.query(
                    query_texts=[query],
                    n_results=min(top_k, 20),
                    where=filters if filters else None,
                )
            results = await asyncio.to_thread(_query_sync)

            passages = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                ids = results["ids"][0]
                docs = results["documents"][0] if results.get("documents") else []
                metas = results["metadatas"][0] if results.get("metadatas") else []
                distances = results["distances"][0] if results.get("distances") else []

                for i, chunk_id in enumerate(ids):
                    text = docs[i] if i < len(docs) else ""
                    meta = metas[i] if i < len(metas) else {}
                    score = 1.0 - (distances[i] if i < len(distances) else 0.0)
                    passages.append({
                        "chunk_id": chunk_id,
                        "text": text,
                        "score": round(max(0.0, score), 4),
                        "doc_id": meta.get("doc_id", "corpus_doc"),
                        "doc_title": meta.get("doc_title", "EIA Notification 2006"),
                        "clause_ref": meta.get("clause_ref", "Schedule"),
                        "metadata": meta,
                    })
            if passages:
                return passages
    except Exception as exc:
        logger.warning("Chroma search unavailable or collection query failed, using fallback passages", error=str(exc))

    # Built-in fallback passages extracted from EIA Notification 2006 corpus
    fallback_passages = [
        {
            "chunk_id": "chunk_schedule_1a",
            "text": "Item 1(a): Mining of minerals. Category A: >= 50 ha of mining lease area in respect of non-coal mine lease. Category B: < 50 ha of mining lease area in respect of non-coal mine lease.",
            "score": 0.95,
            "doc_id": "eia_2006_master",
            "doc_title": "EIA Notification 2006",
            "clause_ref": "Schedule Item 1(a)",
            "metadata": {"item_no": "1(a)", "category": "B", "sector": "Mining"},
        },
        {
            "chunk_id": "chunk_general_condition",
            "text": GENERAL_CONDITION_VERBATIM,
            "score": 0.90,
            "doc_id": "eia_2006_master",
            "doc_title": "EIA Notification 2006",
            "clause_ref": "General Condition",
            "metadata": {"chunk_type": "general_condition", "applies_to_all_schedule_items": True},
        },
    ]
    return fallback_passages[:top_k]


def compare_threshold(value: float, threshold: float, operator: str = "<=") -> bool:
    """Deterministically compare a numeric value against a threshold."""
    if operator in ["<=", "le"]:
        return value <= threshold
    elif operator in ["<", "lt"]:
        return value < threshold
    elif operator in [">=", "ge"]:
        return value >= threshold
    elif operator in [">", "gt"]:
        return value > threshold
    elif operator in ["==", "eq"]:
        return abs(value - threshold) < 1e-6
    return False
