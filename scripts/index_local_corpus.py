"""Index the EIA Notification 2006 corpus into ChromaDB.
Supports local persistent storage as well as remote Chroma servers.
"""

import os
import sys
import asyncio
from libs.common.config import settings
from libs.common.logging import get_logger
from services.ingest.pipeline import discover_pdfs, extract_text, chunk_document, upsert_to_chroma
from services.worker.tools.retrieval import get_chroma_client, corpus_search

logger = get_logger("index_corpus")


def index_corpus(corpus_dir: str = "corpus"):
    print(f"=== Starting Ingestion for Corpus: {corpus_dir} ===")
    pdfs = discover_pdfs(corpus_dir)
    print(f"Discovered {len(pdfs)} PDF documents.")

    all_chunks = []
    for pdf_info in pdfs:
        doc_id = pdf_info["doc_id"]
        doc_title = pdf_info["filename"]
        pdf_path = pdf_info["path"]
        print(f"Processing: {doc_title}...")
        try:
            pages = extract_text(pdf_path)
            chunks = chunk_document(pages, doc_id, doc_title)
            all_chunks.extend(chunks)
            print(f"  -> Extracted {len(pages)} pages, {len(chunks)} chunks.")
        except Exception as exc:
            print(f"  -> Warning: failed to extract {doc_title}: {exc}")

    print(f"\nTotal structured chunks extracted: {len(all_chunks)}")
    print("Upserting chunks into ChromaDB...")
    client = get_chroma_client()
    upserted = upsert_to_chroma(all_chunks)
    print(f"Successfully upserted {upserted} chunks into ChromaDB.")

    collection = client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)
    print(f"Verified Chroma collection '{settings.CHROMA_COLLECTION_NAME}' total items: {collection.count()}")

    return upserted


if __name__ == "__main__":
    count = index_corpus("corpus")
    print("\nTesting semantic retrieval from ChromaDB:")
    sample_queries = [
        "Mining of minerals lease area",
        "General Condition 5 km eco-sensitive zone",
        "Thermal power plant 10 km",
    ]
    for q in sample_queries:
        res = asyncio.run(corpus_search(q, top_k=2))
        print(f"\nQuery: '{q}' -> Retrieved {len(res)} passages:")
        for r in res:
            safe_text = r['text'][:90].encode('ascii', errors='ignore').decode('ascii')
            print(f"  - [{r['chunk_id']}] {r['clause_ref']}: {safe_text}... (Score: {r['score']})")
