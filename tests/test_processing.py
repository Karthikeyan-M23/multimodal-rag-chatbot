import pytest

from src.ingestion import web_processor
from src.ingestion.excel_processor import rows_to_documents
from src.processing.chunker import create_chunks
from src.retrieval.bm25_retriever import BM25Retriever, tokenize
from src.retrieval.citation_formatter import format_timestamp, location_label


def test_rows_are_grouped_with_header_context():
    rows = [["Name", "Age"]] + [[f"P{i}", i] for i in range(60)]
    documents = rows_to_documents(rows, "f.xlsx", "excel", sheet="People")

    assert len(documents) == 3  # 25 rows per group
    first = documents[0]
    assert first["text"].startswith("Sheet: People\nColumns: Name, Age\nRow 2: Name: P0 | Age: 0")
    assert (first["metadata"]["row_start"], first["metadata"]["row_end"]) == (2, 26)
    assert documents[-1]["metadata"]["row_end"] == 61


def test_presplit_rows_are_not_split_by_chunker():
    documents = rows_to_documents([["A"], ["x" * 50]] * 1, "f.csv", "csv", sheet="s")
    chunks = create_chunks(documents)
    assert len(chunks) == 1 and "presplit" not in chunks[0]["metadata"]


def test_transcript_segments_merge_into_windows():
    segments = [
        {"text": f"Sentence number {i}.", "metadata": {
            "file_type": "audio", "content_type": "transcript",
            "start_time": i * 10.0, "end_time": i * 10.0 + 9}}
        for i in range(20)
    ]
    from src.processing.chunker import TRANSCRIPT_MAX_SECONDS

    chunks = create_chunks(segments)

    assert 2 <= len(chunks) < len(segments)
    assert chunks[0]["metadata"]["start_time"] == 0.0
    for chunk in chunks:
        span = chunk["metadata"]["end_time"] - chunk["metadata"]["start_time"]
        assert span <= TRANSCRIPT_MAX_SECONDS
    # Adjacent windows overlap by one segment for continuity.
    last_of_first = chunks[0]["text"].split(". ")[-1]
    assert chunks[1]["text"].startswith(last_of_first.rstrip(".")) or last_of_first in chunks[1]["text"]


def test_long_text_is_split_with_overlap():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = create_chunks([{"text": text, "metadata": {"file_type": "pdf", "page": 1}}])
    assert len(chunks) > 3
    assert all(c["metadata"]["page"] == 1 for c in chunks)
    assert len({c["metadata"]["chunk_index"] for c in chunks}) == len(chunks)


@pytest.mark.parametrize("metadata,label", [
    ({"file_type": "pdf", "page": 4}, "Page 4"),
    ({"file_type": "excel", "sheet": "Q1", "row_start": 2, "row_end": 9}, "Q1 · rows 2–9"),
    ({"file_type": "audio", "content_type": "transcript", "start_time": 65, "end_time": 130}, "01:05–02:10"),
    ({"file_type": "video", "content_type": "frame", "timestamp": 3725}, "Frame at 1:02:05"),
    ({"file_type": "docx", "section": "Leave policy"}, "Leave policy"),
    ({"file_type": "image"}, "Image"),
])
def test_location_labels(metadata, label):
    assert location_label(metadata) == label


def test_timestamp_format():
    assert format_timestamp(59) == "00:59"
    assert format_timestamp(3600) == "1:00:00"


def test_tokenizer_handles_punctuation_plurals_and_ids():
    assert tokenize("Invoices for INV-2024.07, please!") == ["invoice", "inv-2024.07", "please"]
    assert "the" not in tokenize("the zebra")


def test_bm25_ignores_non_matching_chunks():
    retriever = BM25Retriever([
        {"text": "zebras live in africa", "metadata": {"id": 1}},
        {"text": "falcon budget report", "metadata": {"id": 2}},
        {"text": "office opening hours", "metadata": {"id": 3}},
    ])
    results = retriever.retrieve("falcon budget", k=5)
    assert [r["metadata"]["id"] for r in results] == [2]
    assert BM25Retriever([]).retrieve("x") == []


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost:8000", "http://10.0.0.5/",
    "http://169.254.169.254/latest/meta-data", "http://[::1]/",
])
def test_private_addresses_blocked(url, monkeypatch):
    monkeypatch.setattr(web_processor, "ALLOW_PRIVATE_URLS", False)
    with pytest.raises(ValueError, match="private or local"):
        web_processor._check_url(url)


def test_non_http_schemes_blocked():
    with pytest.raises(ValueError, match="http"):
        web_processor._check_url("file:///etc/passwd")


def _doc(score, method, bm25=0.0):
    from langchain_core.documents import Document
    return Document(page_content="x", metadata={
        "rerank_score": score, "retrieval_method": method, "bm25_score": bm25})


def test_evidence_uses_reranker_thresholds():
    from src.vector.vector_retriever import select_evidence
    docs = [_doc(0.9, "vector"), _doc(0.2, "vector"), _doc(0.02, "vector"), _doc(0.001, "vector")]
    # 0.02 is above the absolute floor but below 5% of the best score.
    assert [d.metadata["rerank_score"] for d in select_evidence(docs)] == [0.9, 0.2]


def test_keyword_rescue_only_when_reranker_rejects_all():
    from src.vector.vector_retriever import select_evidence
    rescued = select_evidence([_doc(0.0004, "keyword+vector", bm25=5.7), _doc(0.0001, "vector")])
    assert len(rescued) == 1 and rescued[0].metadata["bm25_score"] == 5.7
    # Weak keyword overlap (common words) is not rescued.
    assert select_evidence([_doc(0.0004, "keyword+vector", bm25=0.8)]) == []
    # Off-topic: no keyword hit at all.
    assert select_evidence([_doc(0.002, "vector")]) == []


def test_follow_up_detection():
    from src.rag_pipeline import needs_rewrite
    assert needs_rewrite("What is its budget?")
    assert needs_rewrite("and the deadline?")
    assert needs_rewrite("Why?")
    assert not needs_rewrite("Which region had the highest Q1 revenue?")
