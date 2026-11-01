"""Offline contracts only: synthetic ranks are never model-quality evidence."""
import asyncio
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval/dataset/rag_quality_v1.jsonl"


def module():
    # A missing implementation is an assertion failure during the initial red run.
    assert (ROOT / "eval/rag_quality.py").is_file(), "RAG quality runner not implemented"
    return importlib.import_module("eval.rag_quality")


def candidate(cid, text="evidence", score=0.5):
    return {"chunk_id": cid, "doc_id": 1, "product_id": -1, "doc_type": "POLICY",
            "source": "policy", "content": text, "score": score}


def fixture_cases():
    return [
        {"id": "p", "split": "dev", "family": "p", "query": "positive question",
         "answerable": True, "label_status": "ai_prelabelled", "gold": [{
             "path": "OFFLINE_FIXTURE_NOT_A_SOURCE", "source_sha256": hashlib.sha256(b"evidence").hexdigest(),
             "source": "policy", "heading": "## rule", "text": "evidence",
             "text_sha256": hashlib.sha256(b"evidence").hexdigest()}]},
        {"id": "n", "split": "heldout", "family": "n", "query": "unknown question",
         "answerable": False, "label_status": "ai_prelabelled", "gold": []},
    ]


class OfflineReader:
    """Only external boundaries are doubled; metric/report logic remains real."""
    def __init__(self):
        self.calls = []
        self.corpus = [candidate(1, "## rule\n\nevidence"), candidate(2, "other")]

    async def snapshot(self):
        return copy.deepcopy(self.corpus)

    async def recall(self, leg, query, top_k):
        self.calls.append((leg, query, top_k))
        return {"hits": copy.deepcopy(self.corpus if leg == "dense" else self.corpus[::-1])}

    def fuse(self, dense, bm25):
        return copy.deepcopy(dense)

    async def rerank(self, query, pool):
        self.calls.append(("rerank", query, [r["chunk_id"] for r in pool]))
        for row in pool:
            row["rerank_score"] = .9
        return pool[::-1]

    def answerability(self, rows):
        return {"answerable": bool(rows), "reason": "fixture", "top1": .9, "margin": 0.0}

    def fingerprints(self):
        return {"provider": "OFFLINE_FIXTURE_NOT_A_MODEL"}

    recall_k = {"dense": 20, "bm25": 20}


def test_rank_math_counts_unretrieved_gold_and_truncates_at_four():
    m = module().ranking_metrics([9, 2, 8, 1, 3], {1, 2, 3})
    assert m["recall@4"] == pytest.approx(2 / 3)
    assert m["mrr@4"] == .5
    assert m["ndcg@4"] == pytest.approx((1 / math.log2(3) + 1 / math.log2(5)) /
                                         (1 + 1 / math.log2(3) + 1 / math.log2(4)))
    assert module().ranking_metrics([], {1}) == {"recall@4": 0, "mrr@4": 0, "ndcg@4": 0}
    assert module().ranking_metrics([1], set()) is None


@pytest.mark.parametrize("ids", [[1, 1], [True], [0], ["1"]])
def test_bad_rank_identifiers_are_not_silently_scored(ids):
    with pytest.raises(ValueError):
        module().ranking_metrics(ids, {1})


def test_gold_resolution_checks_heading_text_hash_not_deployment_ids():
    rq = module()
    cases = fixture_cases()
    corpus = [candidate(987, "## rule\n\nevidence")]
    assert rq.resolve_gold(cases, corpus) == {"p": {987}, "n": set()}
    for replacement in ["## wrong\n\nevidence", "## rule\n\nchanged evidence!"]:
        # The second still contains evidence; an invalid hash must independently fail.
        changed = copy.deepcopy(cases)
        if "changed" in replacement:
            changed[0]["gold"][0]["text_sha256"] = "0" * 64
        with pytest.raises(rq.EnvironmentMismatch):
            rq.resolve_gold(changed, [candidate(987, replacement)])
    with pytest.raises(rq.EnvironmentMismatch):
        rq.resolve_gold(cases, [])  # Missing gold is NOT a zero-recall result.


@pytest.mark.parametrize("change", [
    {"chunk_id": None}, {"score": float("nan")}, {"score": True},
    {"content": "changed"}, {"source": "wrong"}, {"doc_id": True},
])
def test_malformed_or_outdated_candidates_fail_closed(change):
    rq = module()
    corpus = [candidate(1)]
    raw = {**candidate(1), **change}
    with pytest.raises((ValueError, rq.EnvironmentMismatch)):
        rq.validate_candidates({"hits": [raw]}, "dense", corpus)


def test_ties_preserve_provider_order_and_duplicates_are_rejected():
    rq = module()
    corpus = [candidate(1), candidate(2)]
    rows = rq.validate_candidates({"hits": corpus[::-1]}, "dense", corpus)
    assert [r["chunk_id"] for r in rows] == [2, 1]
    with pytest.raises(ValueError):
        rq.validate_candidates({"hits": [corpus[0], corpus[0]]}, "dense", corpus)
    with pytest.raises(ValueError):
        rq.validate_candidates({"error": "unavailable", "hits": []}, "dense", corpus)


def test_frozen_dataset_has_group_disjoint_splits_and_grounded_labels():
    rq = module()
    cases = rq.load_dataset(DATASET)
    assert 24 <= len(cases) <= 30
    assert {c["split"] for c in cases} == {"dev", "heldout"}
    dev = {c["family"] for c in cases if c["split"] == "dev"}
    held = {c["family"] for c in cases if c["split"] == "heldout"}
    assert not dev & held
    assert any(c["label_status"] == "unresolved" for c in cases)
    for c in cases:
        assert c["human_reviewed"] is False
        if c["answerable"] is False:
            assert c["gold"] == []
        if c["answerable"] is True:
            assert c["gold"]
    existing = []
    for name in ["rag_answerability.jsonl", "kb_large_rag.jsonl", "rag.jsonl"]:
        existing.extend(json.loads(line)["query"] for line in (DATASET.parent / name).read_text(
            encoding="utf-8").splitlines() if line.strip())
    assert not {c["query"] for c in cases} & set(existing)


def test_changed_source_hash_and_bad_dataset_labels_fail(tmp_path):
    rq = module()
    cases = rq.load_dataset(DATASET)
    positive = copy.deepcopy(next(c for c in cases if c["answerable"] is True))
    for field, value in [("source_sha256", "0" * 64), ("heading", "## nonexistent")]:
        changed = copy.deepcopy(positive)
        changed["gold"][0][field] = value
        path = tmp_path / "bad.jsonl"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises((ValueError, rq.EnvironmentMismatch)):
            rq.load_dataset(path)
    for change in [{"gold": []}, {"answerable": False}, {"query": ""}]:
        path = tmp_path / "bad.jsonl"
        path.write_text(json.dumps({**positive, **change}), encoding="utf-8")
        with pytest.raises(ValueError):
            rq.load_dataset(path)


def test_offline_ablation_common_pools_provenance_and_negative_denominators():
    rq = module()
    adapter = OfflineReader()
    report = asyncio.run(rq.run_ablation(adapter, fixture_cases(), dataset_sha256="fixed"))
    assert report["status"] == "offline_contract_only"
    assert report["quality"] is None
    assert report["provenance"]["dataset_sha256"] == "fixed"
    assert report["provenance"]["corpus_sha256"]
    assert report["provenance"]["implementation_sha256"]
    assert report["provenance"]["models"]["provider"] == "OFFLINE_FIXTURE_NOT_A_MODEL"
    assert len([c for c in adapter.calls if c[0] == "dense"]) == 2
    assert len([c for c in adapter.calls if c[0] == "bm25"]) == 2
    assert all(isinstance(c[1], str) for c in adapter.calls)  # No case/gold passed to models.
    p, n = report["cases"]
    assert set(p["arms"]) == {"dense_only", "bm25_only", "rrf_hybrid", "rrf_http_reranker"}
    assert p["arms"]["rrf_hybrid"]["ranked_ids"] == [1, 2]
    assert p["arms"]["rrf_http_reranker"]["ranked_ids"] == [2, 1]
    assert p["recalled_pools"]["dense"][0]["content"] == "## rule\n\nevidence"
    assert "rerank_score" not in p["recalled_pools"]["dense"][0]
    assert all(a["ranking"] is None for a in n["arms"].values())
    summary = report["diagnostics"]["all"]["dense_only"]
    assert summary["positive_count"] == 1
    assert summary["negative_count"] == 1
    assert summary["negative_false_accept_rate"] == 1.0
    assert report["latency_ms"]["dense"]["count"] == 2
    assert report["latency_ms"]["rerank"]["p95"] >= 0


def test_fake_cannot_claim_live_and_changed_corpus_cannot_score():
    rq = module()
    with pytest.raises(ValueError, match="live"):
        asyncio.run(rq.run_ablation(OfflineReader(), fixture_cases(), dataset_sha256="fixed", live=True))

    class DriftingReader(OfflineReader):
        async def snapshot(self):
            result = await super().snapshot()
            self.corpus[0]["content"] += "changed"
            return result

    with pytest.raises(rq.EnvironmentMismatch):
        asyncio.run(rq.run_ablation(DriftingReader(), fixture_cases(), dataset_sha256="fixed"))


def test_unresolved_labels_block_scoring_instead_of_becoming_negatives():
    rq = module()
    cases = fixture_cases()
    cases[0].update(answerable=None, label_status="unresolved", gold=[])
    with pytest.raises(rq.EnvironmentMismatch, match="unresolved"):
        asyncio.run(rq.run_ablation(OfflineReader(), cases, dataset_sha256="fixed"))


def test_cli_default_is_validation_only_and_imports_no_app_or_network():
    result = subprocess.run([sys.executable, "-B", "-c", "import sys; from eval.rag_quality import main; "
        "main([]); assert not any(k == 'app' or k.startswith('app.') for k in sys.modules)"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "dataset_validation_only"
    assert report["quality"] is None
    assert report["unresolved_ids"]
    refusal = subprocess.run([sys.executable, "-B", "-m", "eval.rag_quality", "--live"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert refusal.returncode != 0
    assert "ack-read-only" in refusal.stderr


def test_bm25_null_platform_scope_matches_vector_minus_one():
    rq = module()
    row = {**candidate(1), "product_id": None, "docType": "POLICY"}
    row.pop("doc_type")
    parsed = rq.validate_candidates({"hits": [row]}, "bm25", [candidate(1)])
    assert parsed[0]["product_id"] == -1
    assert parsed[0]["bm25_score"] == .5
    for invalid in (True, 0, 12):
        with pytest.raises((ValueError, rq.EnvironmentMismatch)):
            rq.validate_candidates({"hits": [{**row, "product_id": invalid}]}, "bm25", [candidate(1)])


def test_full_reference_source_content_must_match_not_just_an_anchor():
    rq = module()
    cases = rq.load_dataset(DATASET)
    case = next(c for c in cases if c["answerable"] is True)
    source = case["gold"][0]["source"]
    # Isolate the pure chunk-layout boundary; no splitter/model/network is loaded.
    corpus = [{**candidate(1, "expected chunk"), "source": source}]
    rq.validate_reference_corpus([case], corpus, lambda text: ["expected chunk"])
    with pytest.raises(rq.EnvironmentMismatch):
        rq.validate_reference_corpus([case], [{**corpus[0], "content": "expected chunk + conflicting rule"}],
                                     lambda text: ["expected chunk"])
    with pytest.raises(rq.EnvironmentMismatch):
        rq.validate_reference_corpus([case], corpus + [{**corpus[0], "chunk_id": 2, "doc_id": 2}],
                                     lambda text: ["expected chunk"])


def test_missing_http_scores_or_reranker_failure_never_fall_back():
    rq = module()

    class MissingScores(OfflineReader):
        async def rerank(self, query, pool):
            return pool

    class FailingHTTP(OfflineReader):
        async def rerank(self, query, pool):
            raise RuntimeError("HTTP unavailable")

    for reader in (MissingScores(), FailingHTTP()):
        with pytest.raises((ValueError, RuntimeError)) as error:
            asyncio.run(rq.run_ablation(reader, fixture_cases(), dataset_sha256="fixed"))
        assert error.value.report["quality"] is None
        assert error.value.report["status"] == "invalid_run"
        assert error.value.report["cases"][0]["recalled_pools"]


def test_default_live_refuses_unresolved_before_import_or_network():
    result = subprocess.run([sys.executable, "-B", "-m", "eval.rag_quality", "--live", "--ack-read-only"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "environment_mismatch"
    assert "unresolved" in report["error"]
    assert report["quality"] is None


def test_real_fusion_http_client_and_gate_in_offline_transport_contract():
    # Isolated public settings fixture avoids importing app.config's dotenv loader.
    # Real retrieval/RRF, QwenHttpReranker HTTP parsing, and gate run unchanged;
    # only the external transport is synthetic, and the report must say OFFLINE.
    code = r'''
import asyncio, copy, importlib, json, sys, types
from pathlib import Path
from types import SimpleNamespace
root = Path.cwd()
sys.path.insert(0, str(root / 'ai-service'))
config = types.ModuleType('app.config')
config.settings = SimpleNamespace(
    rag_reranker_base_url='http://offline.invalid', rag_reranker_endpoint='/v1/rerank',
    rag_reranker_model='OFFLINE_HTTP_CONTRACT', rag_reranker_api_key='',
    rag_reranker_timeout_s=1., rag_reranker_batch_size=10,
    rag_rrf_top_k=10, rag_rrf_k=60, rag_final_top_k=4,
    rag_answer_min_score=.45, rag_answer_high_confidence_score=.65,
    rag_answer_min_margin=.05, rag_vector_score_center=.45,
    rag_vector_score_scale=.12, rag_bm25_score_scale=8.)
sys.modules['app.config'] = config
from app.rag import retrieval
from app.rag.reranker import QwenHttpReranker
from eval.rag_quality import LiveReader, run_ablation
from eval.tests.test_rag_quality import OfflineReader, fixture_cases, candidate
import httpx
requests = []
def handle(request):
    payload = json.loads(request.content)
    requests.append(payload)
    assert set(payload) == {'model', 'query', 'documents', 'top_n'}
    assert payload['documents'] == ['## rule\n\nevidence', 'other']
    return httpx.Response(200, json={'results': [
        {'index': 1, 'relevance_score': .4},
        {'index': 0, 'relevance_score': .1 if payload['query'] == 'positive question' else .4}]})
original = httpx.AsyncClient
httpx.AsyncClient = lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs)
reader = LiveReader.__new__(LiveReader)
reader.settings, reader.retrieval = config.settings, retrieval
reader.reranker = QwenHttpReranker(config.settings)
fixture = OfflineReader()
reader.recall_k = fixture.recall_k
reader.snapshot, reader.recall = fixture.snapshot, fixture.recall
reader.fingerprints = fixture.fingerprints
report = asyncio.run(run_ablation(reader, fixture_cases(), dataset_sha256='synthetic', live=False))
assert len(requests) == 2
assert report['cases'][1]['arms']['rrf_http_reranker']['ranked_ids'] == [1, 2]  # stable HTTP-score tie
p = report['cases'][0]['arms']
assert p['rrf_hybrid']['ranked_ids'] == [1, 2]  # actual RRF score/best-rank/ID tie
assert p['rrf_http_reranker']['ranked_ids'] == [2, 1]
assert p['rrf_hybrid']['ranking']['recall@4'] == 1
assert p['rrf_http_reranker']['ranking']['recall@4'] == 1
assert not p['rrf_http_reranker']['answerability']['answerable']  # relevant != answerable
assert p['rrf_http_reranker']['answerability']['top1'] == .4
assert report['quality'] is None and report['status'] == 'offline_contract_only'
assert config.settings.rag_answer_min_score == .45  # runtime gate left untouched
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr



def test_live_snapshot_reads_only_current_published_platform_policy_chunks():
    from types import SimpleNamespace
    rq = module()
    calls = []

    class Iterator:
        def __init__(self):
            self.done = False

        def next(self):
            if self.done:
                return []
            self.done = True
            return [{"id": i, "doc_id": 1, "product_id": -1, "doc_type": "POLICY", "content": "policy"}
                    for i in (1, 2)]

        def close(self):
            calls.append("close")

    def query_iterator(**kwargs):
        calls.append(kwargs)
        return Iterator()

    async def kb_current_chunks(ids):
        calls.append(ids)
        return {1: "published title"}  # Chunk 2 is retired, not valid evidence.

    reader = rq.LiveReader.__new__(rq.LiveReader)
    reader.settings = SimpleNamespace(milvus_collection="test_collection")
    reader.store = SimpleNamespace(client=SimpleNamespace(query_iterator=query_iterator))
    reader.backend = SimpleNamespace(kb_current_chunks=kb_current_chunks)
    rows = asyncio.run(reader.snapshot())
    assert [r["chunk_id"] for r in rows] == [1]
    assert rows[0]["source"] == "published title"
    assert calls[0]["filter"] == 'doc_id > 0 and doc_type == "POLICY" and product_id == -1'
    assert calls[0]["output_fields"] == ["id", "doc_id", "product_id", "doc_type", "content"]
    assert calls[1:] == ["close", [1, 2]]


def newline_source_fixture(tmp_path, monkeypatch, frozen_newline=b"\r\n", actual_newline=b"\n"):
    rq = module()
    monkeypatch.setattr(rq, "ROOT", tmp_path)
    source = tmp_path / "backend/src/main/resources/kbseed/policy.md"
    source.parent.mkdir(parents=True)
    canonical = b"## rule\n\nevidence\n"
    source.write_bytes(canonical.replace(b"\n", actual_newline))
    cases = fixture_cases()[:1]
    cases[0].update(version=1, human_reviewed=False)
    cases[0]["gold"][0].update(
        path=source.relative_to(tmp_path).as_posix(),
        source_sha256=hashlib.sha256(canonical.replace(b"\n", frozen_newline)).hexdigest())
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(json.dumps(cases[0]) + "\n", encoding="utf-8")
    return rq, source, cases, dataset, canonical


@pytest.mark.parametrize("frozen_newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("actual_newline", [b"\n", b"\r\n"])
def test_frozen_source_accepts_only_lf_crlf_representations(tmp_path, monkeypatch, frozen_newline, actual_newline):
    rq, source, cases, dataset, canonical = newline_source_fixture(
        tmp_path, monkeypatch, frozen_newline, actual_newline)
    assert rq.load_dataset(dataset) == cases  # Frozen raw expected hash remains unchanged.
    corpus = [candidate(1, canonical.decode("utf-8"))]
    def split_source(text):
        assert text == canonical.decode("utf-8")
        return [text]
    rq.validate_reference_corpus(cases, corpus, split_source)


@pytest.mark.parametrize("changed", [
    b"## rule\n\nevidence changed\n", b"## rule\n\nevidence \n",
    b"\xef\xbb\xbf## rule\n\nevidence\n", b"## rule\n\nevidence\n\n",
    b"## rule\r\revidence\r",
])
def test_frozen_source_refuses_content_whitespace_bom_and_lone_cr(tmp_path, monkeypatch, changed):
    rq, source, cases, dataset, canonical = newline_source_fixture(tmp_path, monkeypatch)
    source.write_bytes(changed)
    with pytest.raises(rq.EnvironmentMismatch, match="source"):
        rq.load_dataset(dataset)
    with pytest.raises(rq.EnvironmentMismatch, match="source"):
        rq.validate_reference_corpus(cases, [candidate(1, canonical.decode())], lambda text: [text])


def test_new_live_provenance_distinguishes_raw_and_canonical_lf_hashes(tmp_path, monkeypatch):
    from types import SimpleNamespace
    rq, source, cases, dataset, canonical = newline_source_fixture(tmp_path, monkeypatch)
    class LocalReader(OfflineReader):
        def __init__(self):
            super().__init__()
            self.corpus = [candidate(1, canonical.decode())]
    monkeypatch.setattr(rq, "LiveReader", LocalReader)
    monkeypatch.setitem(sys.modules, "app.rag.ingest", SimpleNamespace(split_text=lambda text: [text]))
    report = asyncio.run(rq.run_ablation(LocalReader(), cases, dataset_sha256="fixture", live=True))
    provenance = report["provenance"]
    ref = cases[0]["gold"][0]
    assert provenance["reference_source_sha256"][ref["path"]] == ref["source_sha256"]
    source_provenance = provenance["reference_source_provenance"][ref["path"]]
    assert source_provenance == {
        "actual_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "reference_sha256": ref["source_sha256"],
        "actual_canonical_lf_sha256": hashlib.sha256(canonical).hexdigest(),
        "reference_canonical_lf_sha256": hashlib.sha256(canonical).hexdigest(),
        "match_mode": "lf_crlf_equivalent",
    }
    assert source_provenance["actual_sha256"] != source_provenance["reference_sha256"]
