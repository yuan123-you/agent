import hashlib
import json
from collections import Counter
from pathlib import Path

from backend.scripts.kb_dataset import build_dataset, write_dataset


def _digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_build_dataset_targets_one_thousand_chunks_with_diverse_documents():
    docs = build_dataset()
    assert len(docs) == 15
    assert set(d.doc_type for d in docs) == {"FAQ", "INTRO", "POLICY"}
    assert set(d.file_format for d in docs) == {"MD", "TXT", "PDF"}
    assert len({d.topic for d in docs}) == 15
    assert len({d.key for d in docs}) == 15
    assert len({d.title for d in docs}) == 15
    # The generator estimate is conservative; real split_text verification targets 900-1,100.
    estimated = sum(d.estimated_chunks for d in docs)
    assert 550 <= estimated <= 750


def test_write_dataset_is_deterministic_and_manifest_references_real_files(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_dataset(first, tmp_path / "first.jsonl")
    write_dataset(second, tmp_path / "second.jsonl")
    assert _digest_tree(first) == _digest_tree(second)

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert len(manifest["documents"]) == 15
    for item in manifest["documents"]:
        path = first / item["resource"].removeprefix("kbseed/generated/")
        assert path.is_file()
        assert path.stat().st_size > 100
        assert item["charCount"] > 0
        assert item["estimatedChunkCount"] > 0


def test_eval_rows_cover_all_difficulties_and_reference_document_content(tmp_path):
    output = tmp_path / "corpus"
    eval_path = tmp_path / "eval.jsonl"
    write_dataset(output, eval_path)
    docs_by_key = {doc.key: doc for doc in build_dataset()}
    rows = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 15
    assert {row["difficulty"] for row in rows} == {
        "direct", "paraphrase", "conditional", "multi_hop", "temporal_region", "hard_negative"
    }
    assert all(row["expected_doc_key"] and row["must_hit"] for row in rows)
    assert all(
        all(expected in docs_by_key[row["expected_doc_key"]].content for expected in row["must_hit"])
        for row in rows
    )
