"""Keep retrieval labels aligned with the current simulated after-sale contract."""
import json
from pathlib import Path

import pytest

from backend.scripts.kb_dataset import build_dataset


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "dataset" / "kb_large_rag.jsonl"


def rows():
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("row_number,key,expected", [
    (3, "payment-refund", ["模拟退款", "SIM-"]),
    (9, "seven-day-return", ["不配置统一七天", "人工核实"]),
    (10, "quality-exchange", ["人工审核", "原 SKU"]),
])
def test_after_sale_retrieval_labels_require_supported_current_behavior(row_number, key, expected):
    row = rows()[row_number - 1]
    assert row["expected_doc_key"] == key
    assert row["must_hit"] == expected
    content = (ROOT / "backend" / "src" / "main" / "resources" / "kbseed" / "generated" / "docs" / f"{key}.md").read_text(encoding="utf-8")
    assert all(phrase in content for phrase in row["must_hit"])


def test_committed_retrieval_labels_match_current_pure_generator():
    documents = build_dataset()
    actual = rows()
    assert len(actual) == len(documents)
    for row, doc in zip(actual, documents, strict=True):
        assert row["expected_doc_key"] == doc.key
        assert row["query"] == doc.query
        assert row["doc_type"] == doc.doc_type
        assert row["must_hit"] == list(doc.must_hit)
