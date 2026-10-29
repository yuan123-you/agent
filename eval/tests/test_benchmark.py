"""客服标准评测集与评测引擎的自动化回归测试"""
import json
import pytest
from pathlib import Path

from eval.benchmark import CustomerServiceBenchmark, DEFAULT_BENCHMARK_PATH


def test_benchmark_dataset_integrity():
    bench = CustomerServiceBenchmark(DEFAULT_BENCHMARK_PATH)
    cases = bench.load_dataset()
    assert len(cases) >= 60, f"Expected at least 60 cases, got {len(cases)}"
    
    seen_ids = set()
    categories = set()
    required_keys = {"id", "category", "scenario", "query", "expected_intent", "expected_route"}

    for case in cases:
        # 1. 字段完整性
        assert required_keys.issubset(case.keys()), f"Missing required keys in case {case.get('id')}"
        # 2. ID 唯一性
        cid = case["id"]
        assert cid not in seen_ids, f"Duplicate case ID: {cid}"
        seen_ids.add(cid)
        # 3. 分类有效性
        cat = case["category"]
        categories.add(cat)
        assert cat in {"PRE_SALES", "ORDER_FULFILLMENT", "AFTER_SALES_POLICY", "EMPATHY_ESCALATION", "MULTI_TURN_PERSONA", "SAFETY_GUARD"}
        # 4. 路由合法性
        assert case["expected_route"] in {"agent", "small_talk", "escalate_node"}
        # 5. 意图合法性
        assert case["expected_intent"] in {"PRODUCT_CONSULT", "ORDER_QUERY", "ORDER_CREATE", "AFTER_SALE_FAQ", "SMALL_TALK", "ASSISTANT_META", "HUMAN_REQUEST"}

    # 确保涵盖全部 6 个客服场景维度
    assert categories == {"PRE_SALES", "ORDER_FULFILLMENT", "AFTER_SALES_POLICY", "EMPATHY_ESCALATION", "MULTI_TURN_PERSONA", "SAFETY_GUARD"}


def test_benchmark_evaluator_runs_and_produces_valid_reports(tmp_path):
    bench = CustomerServiceBenchmark(DEFAULT_BENCHMARK_PATH)
    report = bench.evaluate_all(mode="offline")
    
    assert report.total_cases >= 60
    assert report.overall_pass_rate >= 0.9, f"Pass rate too low: {report.overall_pass_rate}"
    assert report.overall_score >= 90.0, f"Score too low: {report.overall_score}"
    assert report.safety_compliance_rate == 1.0, f"Safety violation detected: {report.safety_compliance_rate}"
    assert len(report.scorecards) == 6

    # 验证报告生成
    json_path, md_path = bench.save_reports(report, output_dir=tmp_path)
    assert json_path.exists()
    assert md_path.exists()

    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_json["overall_score"] == report.overall_score
    assert len(saved_json["scorecards"]) == 6

    saved_md = md_path.read_text(encoding="utf-8")
    assert "# AI Mall 电商客服标准评测基准报告" in saved_md
    assert "PRE_SALES" in saved_md
    assert "SAFETY_GUARD" in saved_md
