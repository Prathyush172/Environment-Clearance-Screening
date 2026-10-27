"""Unit tests for structure-aware chunker."""

from services.ingest.chunker import (
    detect_schedule_table,
    detect_general_condition,
    make_general_condition_chunk,
    extract_schedule_rows,
    make_schedule_chunk,
    chunk_prose,
)


def test_detect_schedule_table():
    sample_text = """
    SCHEDULE (See paragraph 2 and 7)
    LIST OF PROJECTS OR ACTIVITIES REQUIRING PRIOR ENVIRONMENTAL CLEARANCE
    (1) Item No. (2) Project or Activity (3) Category A threshold (4) Category B threshold
    """
    assert detect_schedule_table(sample_text) is True

    non_schedule = "This is a random gazette announcement with general regulations."
    assert detect_schedule_table(non_schedule) is False


def test_detect_general_condition():
    sample_text = """
    General Condition (GC): Any project or activity specified in Category 'B' will be appraised
    at the Central Level as Category 'A', if located in whole or in part within 5 km from the boundary of:
    (i) Protected Areas notified under the Wild Life (Protection) Act, 1972...
    Specific Condition:
    """
    gc = detect_general_condition(sample_text)
    assert gc is not None
    assert "General Condition" in gc
    assert "5 km" in gc


def test_make_general_condition_chunk():
    gc_text = "General Condition (GC): Any project in Category B within 5 km of protected area..."
    chunk = make_general_condition_chunk(gc_text, doc_id="doc1", doc_title="EIA 2006", page=29)
    assert chunk["chunk_type"] == "general_condition"
    assert chunk["applies_to_all_schedule_items"] is True
    assert chunk["metadata"]["primary_distance_km"] == 5.0
    assert chunk["clause_ref"] == "General Condition"


def test_make_schedule_chunk():
    row = {
        "item_no": "1(a)",
        "project_or_activity": "Mining of minerals",
        "category_a": ">= 50 ha lease area",
        "category_b": "< 50 ha lease area",
        "conditions": "General Condition applies",
    }
    chunk = make_schedule_chunk(row, doc_id="doc1", doc_title="EIA 2006", page=18)
    assert "Item 1(a)" in chunk["text"]
    assert "Mining of minerals" in chunk["text"]
    assert chunk["metadata"]["item_no"] == "1(a)"


def test_chunk_prose():
    text = "word " * 1000
    chunks = chunk_prose(text, max_tokens=200, overlap=20)
    assert len(chunks) > 1
    # Check that overlap exists
    assert len(chunks[0].split()) > 50
