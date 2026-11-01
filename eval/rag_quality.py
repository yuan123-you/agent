"""Read-only RAG ablation evidence; default is local dataset validation, not accuracy.

No app imports or network until --live --ack-read-only. Gold is frozen before
recall; corpus mismatch, malformed results, or reranker failure invalidate quality.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "eval/dataset/rag_quality_v1.jsonl"
ARMS = ("dense_only", "bm25_only", "rrf_hybrid", "rrf_http_reranker")


class EnvironmentMismatch(ValueError):
    """No quality score may be claimed for a different or unresolved corpus."""


def sha256(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def _source_provenance(data, expected_sha256):
    """Match the frozen byte hash exactly or through LF/CRLF representation only."""
    canonical = data.replace(b"\r\n", b"\n")
    variants = {sha256(value): value for value in (data, canonical, canonical.replace(b"\n", b"\r\n"))}
    if expected_sha256 not in variants:
        raise EnvironmentMismatch("canonical source hash mismatch")
    actual_sha256 = sha256(data)
    return {
        "actual_sha256": actual_sha256,
        "reference_sha256": expected_sha256,
        "actual_canonical_lf_sha256": sha256(canonical),
        "reference_canonical_lf_sha256": sha256(variants[expected_sha256].replace(b"\r\n", b"\n")),
        "match_mode": "exact_bytes" if actual_sha256 == expected_sha256 else "lf_crlf_equivalent",
    }


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))


def _ids(values):
    values = list(values)
    if any(type(i) is not int or i <= 0 for i in values) or len(set(values)) != len(values):
        raise ValueError("rank identifiers must be unique positive integers")
    return values


def ranking_metrics(ranked_ids, gold_ids):
    """Binary, chunk-level Recall/MRR/nDCG@4; empty gold has no ranking metric."""
    ranked, gold = _ids(ranked_ids), set(_ids(gold_ids))
    if not gold:
        return None
    gains = [int(cid in gold) for cid in ranked[:4]]
    dcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(4, len(gold))))
    return {"recall@4": sum(gains) / len(gold),
            "mrr@4": next((1 / (i + 1) for i, gain in enumerate(gains) if gain), 0.0),
            "ndcg@4": dcg / ideal}


def _heading_present(content, heading):
    # Some canonical headings have their first numbered sentence on the same line.
    return any(line.startswith(heading) for line in content.splitlines())


def load_dataset(path=DEFAULT_DATASET):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    seen, queries, families = set(), set(), {}
    for row in rows:
        cid, query, split = row.get("id"), row.get("query"), row.get("split")
        if (not isinstance(cid, str) or not cid or cid in seen or not isinstance(query, str)
                or not query.strip() or query in queries or split not in ("dev", "heldout")
                or not isinstance(row.get("family"), str) or not row["family"]
                or row.get("version") != 1 or row.get("human_reviewed") is not False):
            raise ValueError("malformed, duplicate, or unsupported dataset case")
        seen.add(cid)
        queries.add(query)
        family = row["family"]
        if family in families and families[family] != split:
            raise ValueError("family leakage across dev/heldout")
        families[family] = split
        gold, label = row.get("gold"), row.get("label_status")
        answerable = row.get("answerable")
        if not isinstance(gold, list) or label not in ("ai_prelabelled", "unresolved"):
            raise ValueError("missing gold or unsupported label status")
        if label == "unresolved":
            if answerable is not None or gold:
                raise ValueError("unresolved cases must not become positive or negative labels")
        elif type(answerable) is not bool or bool(gold) != answerable:
            raise ValueError("positive cases need gold; negative cases need empty gold")
        for ref in gold:
            if any(not isinstance(ref.get(k), str) or not ref[k] for k in
                   ("path", "source", "heading", "text", "text_sha256", "source_sha256")):
                raise ValueError("incomplete gold reference")
            source = (ROOT / ref["path"]).resolve()
            allowed = (ROOT / "backend/src/main/resources/kbseed").resolve()
            if not source.is_relative_to(allowed):
                raise ValueError("gold source must be a canonical KB seed resource")
            if not source.is_file():
                raise EnvironmentMismatch(f"canonical source hash mismatch for {cid}")
            _source_provenance(source.read_bytes(), ref["source_sha256"])
            text = source.read_text(encoding="utf-8")
            start = next((i for i, line in enumerate(text.splitlines()) if line.startswith(ref["heading"])), None)
            if start is None:
                raise EnvironmentMismatch(f"canonical heading missing for {cid}")
            section = []
            for line in text.splitlines()[start:]:
                if section and line.startswith("#"):
                    break
                section.append(line)
            if ref["text"] not in "\n".join(section) or sha256(ref["text"]) != ref["text_sha256"]:
                raise EnvironmentMismatch(f"canonical evidence text/hash mismatch for {cid}")
    if not rows:
        raise ValueError("dataset is empty")
    return rows


def _corpus_index(corpus):
    index = {}
    for row in corpus:
        _ids([row.get("chunk_id")])
        if (row["chunk_id"] in index or type(row.get("doc_id")) is not int or row["doc_id"] <= 0
                or not isinstance(row.get("source"), str) or not row["source"]
                or not isinstance(row.get("content"), str) or not row["content"].strip()
                or row.get("doc_type") != "POLICY"
                or (row.get("product_id") is not None and
                    (type(row["product_id"]) is not int or row["product_id"] != -1))):
            raise ValueError("invalid or duplicate published policy chunk")
        index[row["chunk_id"]] = row
    return index


def validate_reference_corpus(cases, corpus, split_source):
    """Require the full referenced published document to match canonical chunks.

    Source hashes are frozen in the dataset; chunk hashes are derived using the
    deployed pure splitter and unchanged chunk-size/overlap, never query outputs.
    """
    references = {(ref["path"], ref["source"]): ref for c in cases for ref in c["gold"]}
    for (path, title), ref in references.items():
        data = (ROOT / path).read_bytes()
        _source_provenance(data, ref["source_sha256"])
        expected = Counter(sha256(chunk) for chunk in split_source(data.replace(b"\r\n", b"\n").decode("utf-8")))
        published = [row for row in corpus if row["source"] == title]
        actual = Counter(sha256(row["content"]) for row in published)
        if actual != expected or len({row["doc_id"] for row in published}) != 1:
            raise EnvironmentMismatch("full referenced source/chunk hashes differ from canonical KB seed")


def resolve_gold(cases, corpus):
    """Bind predeclared source/heading/exact evidence to independently read IDs.

    This happens BEFORE any query recall. No use of scores or ranked outputs.
    """
    _corpus_index(corpus)
    resolved = {}
    for case in cases:
        if case["label_status"] == "unresolved":
            raise EnvironmentMismatch(f"unresolved label: {case['id']}")
        ids = set()
        for ref in case["gold"]:
            if sha256(ref["text"]) != ref["text_sha256"]:
                raise EnvironmentMismatch(f"reference hash mismatch: {case['id']}")
            matches = [c["chunk_id"] for c in corpus if c["source"] == ref["source"]
                       and _heading_present(c["content"], ref["heading"]) and ref["text"] in c["content"]]
            if not matches:
                raise EnvironmentMismatch(f"published heading/text/source missing: {case['id']}")
            ids.update(matches)
        if bool(ids) != case["answerable"]:
            raise ValueError("gold and answerability disagree")
        resolved[case["id"]] = ids
    return resolved


def validate_candidates(payload, leg, corpus):
    if (leg not in ("dense", "bm25") or not isinstance(payload, dict) or "error" in payload
            or not isinstance(payload.get("hits"), list)):
        raise ValueError("retrieval unavailable or malformed")
    index, rows = _corpus_index(corpus), copy.deepcopy(payload["hits"])
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("candidate must be an object")
        if "docType" in row:
            row["doc_type"] = row.pop("docType")
        # SQL stores platform-wide scope as NULL; the vector schema uses -1.
        if "product_id" not in row or (row["product_id"] is not None and
                (type(row["product_id"]) is not int or row["product_id"] != -1)):
            raise ValueError("candidate is not a platform-wide policy chunk")
        row["product_id"] = -1
        score = row.get("score")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("candidate must have a finite numeric score")
        if type(row.get("doc_id")) is not int:
            raise ValueError("candidate must have a numeric document ID")
        _ids([row.get("chunk_id")])
        current = index.get(row["chunk_id"])
        if current is None or any(row.get(k) != current.get(k) for k in
                                  ("doc_id", "product_id", "doc_type", "source", "content")):
            raise EnvironmentMismatch("recalled chunk differs from published corpus snapshot")
        row["vector_score" if leg == "dense" else "bm25_score"] = float(score)
    _ids(r["chunk_id"] for r in rows)
    # Do not sort on rounded provider scores: stable incoming order breaks ties.
    return rows


def _check_ranking(rows, pool, *, reranked=False):
    ids = _ids(r["chunk_id"] for r in rows)
    original = {r["chunk_id"]: r for r in pool}
    if reranked and set(ids) != set(original):
        raise ValueError("HTTP reranker must score the entire common RRF pool")
    for row in rows:
        if row["chunk_id"] not in original or any(row[k] != original[row["chunk_id"]][k]
                for k in ("content", "source", "doc_id", "product_id", "doc_type")):
            raise EnvironmentMismatch("ranking changed candidate identity or content")
        if reranked:
            score = row.get("rerank_score")
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("missing real HTTP reranker score")
    if reranked and any(rows[i]["rerank_score"] < rows[i + 1]["rerank_score"] for i in range(len(rows) - 1)):
        raise ValueError("HTTP reranker returned non-descending scores")


def distribution(samples):
    values = sorted(samples)
    def quantile(q):
        pos = (len(values) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)
    return {"count": len(values), "samples": samples, "p50": quantile(.5) if values else None,
            "p95": quantile(.95) if values else None, "max": max(values) if values else None}


def _summarize(results):
    summaries = {}
    for split in ("dev", "heldout", "all"):
        selected = [r for r in results if split == "all" or r["split"] == split]
        summaries[split] = {}
        for arm in ARMS:
            positives = [r["arms"][arm] for r in selected if r["expected_answerable"]]
            negatives = [r["arms"][arm] for r in selected if not r["expected_answerable"]]
            summaries[split][arm] = {
                "positive_count": len(positives), "negative_count": len(negatives),
                **{metric: sum(p["ranking"][metric] for p in positives) / len(positives) if positives else None
                   for metric in ("recall@4", "mrr@4", "ndcg@4")},
                "positive_answerable_rate": sum(p["answerability"]["answerable"] for p in positives) / len(positives) if positives else None,
                "negative_false_accept_rate": sum(n["answerability"]["answerable"] for n in negatives) / len(negatives) if negatives else None,
                "negative_rejection_rate": sum(not n["answerability"]["answerable"] for n in negatives) / len(negatives) if negatives else None,
            }
    return summaries


async def run_ablation(reader, cases, *, dataset_sha256, live=False):
    """One recall per leg/case, one common fused pool; fixtures never claim quality."""
    if live and type(reader) is not LiveReader:
        raise ValueError("live quality requires the concrete read-only LiveReader")
    # Refuse unresolved labels even if the adapter could retrieve plausible answers.
    if any(c["label_status"] == "unresolved" for c in cases):
        raise EnvironmentMismatch("unresolved labels require adjudication or explicit exclusion")
    report = {"schema_version": 1, "status": "running", "quality": None, "cases": [], "provenance": {
        "generated_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
        "dataset_sha256": dataset_sha256, "selected_cases_sha256": fingerprint(cases),
        "implementation_sha256": sha256(Path(__file__).read_bytes()),
        "models": reader.fingerprints(), "label_review": "AI-prelabelled; NOT human-reviewed",
        "interpretation": "Binary relevance against frozen, potentially incomplete AI labels; not answer correctness or model accuracy.",
        "measurement": "actual_live_read_only" if live else "offline_contract_only",
        "case_order": [c["id"] for c in cases], "repeats": 1, "warmup": "none",
        "recall_k": reader.recall_k, "scope": {"doc_type": "POLICY", "product_id": -1},
    }}
    timings = {name: [] for name in ("snapshot", "dense", "bm25", "parallel_recall", "fusion", "rerank", "case_total")}
    async def timed(name, call):
        start = perf_counter()
        try:
            return await call
        finally:
            timings[name].append((perf_counter() - start) * 1000)
    try:
        corpus = await timed("snapshot", reader.snapshot())
        corpus = sorted(corpus, key=lambda r: r["chunk_id"])
        _corpus_index(corpus)
        report["provenance"].update(corpus_sha256=fingerprint(corpus), corpus_chunk_count=len(corpus),
            reference_source_sha256={ref["path"]: ref["source_sha256"] for c in cases for ref in c["gold"]},
            corpus_manifest=[{k: c[k] for k in ("chunk_id", "doc_id", "source", "doc_type", "product_id")}
                             | {"content_sha256": sha256(c["content"])} for c in corpus])
        if live:
            report["provenance"]["reference_source_provenance"] = {
                ref["path"]: _source_provenance((ROOT / ref["path"]).read_bytes(), ref["source_sha256"])
                for case in cases for ref in case["gold"]
            }
            from app.rag.ingest import split_text
            validate_reference_corpus(cases, corpus, split_text)
        report["provenance"]["full_reference_corpus_validated"] = live
        gold = resolve_gold(cases, corpus)
        report["provenance"]["gold_bindings"] = {cid: sorted(ids) for cid, ids in gold.items()}
        for case in cases:
            start = perf_counter()
            query = case["query"]
            raw = {"id": case["id"], "query": query, "split": case["split"],
                   "expected_answerable": case["answerable"], "gold_ids": sorted(gold[case["id"]]),
                   "gold_references": case["gold"], "arms": {}}
            offsets = {name: len(values) for name, values in timings.items()}
            report["cases"].append(raw)
            recall_start = perf_counter()
            dense_raw, bm25_raw = await asyncio.gather(*[
                timed(leg, reader.recall(leg, query, reader.recall_k[leg])) for leg in ("dense", "bm25")])
            timings["parallel_recall"].append((perf_counter() - recall_start) * 1000)
            dense = validate_candidates(dense_raw, "dense", corpus)
            bm25 = validate_candidates(bm25_raw, "bm25", corpus)
            raw["recalled_pools"] = copy.deepcopy({"dense": dense, "bm25": bm25})
            fusion_start = perf_counter()
            fused = reader.fuse(copy.deepcopy(dense), copy.deepcopy(bm25))
            timings["fusion"].append((perf_counter() - fusion_start) * 1000)
            _check_ranking(fused, dense + bm25)
            raw["rrf_pool"] = copy.deepcopy(fused)
            # Score the entire fused pool, not just the coarse top four. No fallback.
            ranked = await timed("rerank", reader.rerank(query, copy.deepcopy(fused)))
            _check_ranking(ranked, fused, reranked=True)
            for arm, pool in zip(ARMS, (dense, bm25, fused, ranked), strict=True):
                top = copy.deepcopy(pool[:4])
                decision = reader.answerability(top)
                if type(decision.get("answerable")) is not bool:
                    raise ValueError("invalid answerability decision")
                ids = [r["chunk_id"] for r in top]
                raw["arms"][arm] = {"ranked_ids": ids, "ranking": ranking_metrics(ids, gold[case["id"]]),
                                     "answerability": decision, "candidates": top}
            timings["case_total"].append((perf_counter() - start) * 1000)
            raw["latency_ms"] = {name: values[offsets[name]:] for name, values in timings.items()
                                 if len(values) > offsets[name]}
        after = sorted(await timed("snapshot", reader.snapshot()), key=lambda r: r["chunk_id"])
        if fingerprint(after) != report["provenance"]["corpus_sha256"]:
            raise EnvironmentMismatch("published corpus changed during run")
        scored_pairs = sum(len(case["rrf_pool"]) for case in report["cases"])
        report["provenance"]["reranked_candidate_pairs"] = scored_pairs
        if live and not scored_pairs:
            raise ValueError("no real HTTP reranker scores observed; not four-arm live evidence")
        summaries = _summarize(report["cases"])
        report.update(status="measured_live" if live else "offline_contract_only",
                      quality=summaries if live else None, diagnostics=None if live else summaries)
        report["latency_ms"] = {k: distribution(v) for k, v in timings.items()}
        return report
    except Exception as exc:
        report.update(status="environment_mismatch" if isinstance(exc, EnvironmentMismatch) else "invalid_run",
                      latency_ms={k: distribution(v) for k, v in timings.items()})
        exc.report = report
        raise


class LiveReader:
    """Only published-policy reads + existing query encoder + real HTTP reranker.

    Never calls pipeline factories, ingestion, ensure_collection, agent, chat,
    transaction, trace-export, model-download, or corpus-write operations.
    """
    def __init__(self):
        # This is intentionally the only app import boundary, after CLI opt-in.
        sys.path.insert(0, str(ROOT / "ai-service"))
        from app.config import settings
        from app.clients.backend_client import backend_client
        from app.rag import retrieval
        from app.rag.reranker import QwenHttpReranker
        from app.rag.vectorstore import get_vectorstore

        if not settings.rag_reranker_enabled:
            raise ValueError("live requires the configured real HTTP RAG reranker enabled")
        if settings.rag_final_top_k != 4:
            raise ValueError("this @4 experiment requires the existing final_top_k=4")
        self.settings, self.backend, self.retrieval = settings, backend_client, retrieval
        self.store = get_vectorstore()  # Constructor connects; does NOT ensure/create collection.
        self.reranker = QwenHttpReranker(settings)
        self.recall_k = {"dense": settings.rag_vector_recall_k, "bm25": settings.rag_bm25_recall_k}

    def fingerprints(self):
        s = self.settings
        names = ("embedding_provider", "embedding_model", "embedding_dim", "milvus_collection",
                 "rag_reranker_model", "rag_reranker_endpoint", "rag_reranker_batch_size", "rag_reranker_timeout_s",
                 "rag_vector_recall_k", "rag_bm25_recall_k", "rag_rrf_k", "rag_rrf_top_k", "rag_final_top_k",
                 "rag_answer_min_score", "rag_answer_high_confidence_score", "rag_answer_min_margin",
                 "rag_vector_score_center", "rag_vector_score_scale", "rag_bm25_score_scale",
                 "rag_chunk_size", "rag_chunk_overlap")
        sources = ("rag/retrieval.py", "rag/reranker.py", "rag/vectorstore.py", "rag/ingest.py",
                   "clients/backend_client.py", "clients/llm.py")
        return {"configured": {name: getattr(s, name) for name in names},
                "source_sha256": {name: sha256((ROOT / "ai-service/app" / name).read_bytes()) for name in sources},
                "weight_fingerprints": "unverified: identifiers are configuration, not weight hashes",
                "thresholds": "unchanged runtime settings; no calibration or tuning in this runner"}

    async def snapshot(self):
        def read():
            iterator = self.store.client.query_iterator(
                collection_name=self.settings.milvus_collection,
                filter='doc_id > 0 and doc_type == "POLICY" and product_id == -1',
                output_fields=["id", "doc_id", "product_id", "doc_type", "content"], batch_size=256)
            rows = []
            try:
                while batch := iterator.next():
                    rows.extend(batch)
            finally:
                iterator.close()
            return rows
        rows = await asyncio.to_thread(read)
        published = {}
        for start in range(0, len(rows), 128):
            published.update(await self.backend.kb_current_chunks([r["id"] for r in rows[start:start + 128]]))
        return [{"chunk_id": r["id"], "doc_id": r["doc_id"], "product_id": r["product_id"],
                 "doc_type": r["doc_type"], "content": r["content"], "source": published[r["id"]]}
                for r in rows if r["id"] in published]

    async def recall(self, leg, query, top_k):
        query = self.retrieval.normalize_query(query)
        search = self.store.search if leg == "dense" else self.backend.kb_keyword_search
        return await search(query, doc_type="POLICY", product_id=-1, top_k=top_k)

    def _candidate(self, row):
        keys = ("chunk_id", "doc_id", "product_id", "doc_type", "content", "source")
        return self.retrieval.RetrievalCandidate(**{k: row[k] for k in keys},
            **{k: row[k] for k in ("vector_score", "bm25_score", "rrf_score", "rerank_score") if k in row})

    @staticmethod
    def _row(candidate):
        from dataclasses import asdict
        row = asdict(candidate)
        row["matched_by"] = sorted(row["matched_by"])
        return row

    def fuse(self, dense, bm25):
        return [self._row(c) for c in self.retrieval.reciprocal_rank_fusion(
            [("vector", [self._candidate(r) for r in dense]), ("bm25", [self._candidate(r) for r in bm25])],
            limit=self.settings.rag_rrf_top_k, rrf_k=self.settings.rag_rrf_k)]

    async def rerank(self, query, pool):
        ranked = await self.reranker.rerank(self.retrieval.normalize_query(query), [self._candidate(r) for r in pool])
        return [self._row(c) for c in ranked]

    def answerability(self, rows):
        from dataclasses import asdict
        return asdict(self.retrieval.assess_answerability([self._candidate(r) for r in rows]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--live", action="store_true", help="actually read the configured published KB")
    parser.add_argument("--ack-read-only", action="store_true", help="explicitly authorize live read calls")
    parser.add_argument("--exclude-unresolved", action="store_true", help="explicitly report and exclude unresolved labels")
    parser.add_argument("--split", choices=("dev", "heldout", "all"), default="all")
    args = parser.parse_args(argv)
    if args.live and not args.ack_read_only:
        parser.error("--live requires --ack-read-only; offline/fake runs are not live quality")
    selection = {}
    try:
        cases = load_dataset(args.dataset)
        dataset_hash = sha256(args.dataset.read_bytes())
        unresolved = [c["id"] for c in cases if c["label_status"] == "unresolved"]
        selected = [c for c in cases if args.split == "all" or c["split"] == args.split]
        excluded = [c["id"] for c in selected if c["label_status"] == "unresolved"] if args.exclude_unresolved else []
        selected = [c for c in selected if c["id"] not in excluded]
        if not selected:
            raise ValueError("no selected cases")
        selection = {"split": args.split, "excluded_unresolved_ids": excluded, "all_unresolved_ids": unresolved}
        if args.live:
            # Fail before app imports / network if unresolved cases were not excluded.
            if any(c["label_status"] == "unresolved" for c in selected):
                raise EnvironmentMismatch("unresolved labels require review or --exclude-unresolved")
            async def run():
                return await run_ablation(LiveReader(), selected, dataset_sha256=dataset_hash, live=True)
            report = asyncio.run(run())
            report["provenance"]["selection"] = selection
        else:
            report = {"status": "dataset_validation_only", "quality": None, "cases": len(cases),
                      "dataset_sha256": dataset_hash, "unresolved_ids": unresolved, "selection": selection,
                      "label_review": "AI-prelabelled; NOT human-reviewed; no models executed"}
    except Exception as exc:
        report = getattr(exc, "report", {"status": "environment_mismatch" if isinstance(exc, EnvironmentMismatch)
                                        else "invalid_run", "quality": None})
        report.setdefault("provenance", {})["selection"] = selection
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc) if isinstance(exc, EnvironmentMismatch) else "Run invalid; no quality evidence claimed."
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        raise SystemExit(2)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
