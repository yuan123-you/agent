"""客服标准评测集与评测引擎的工业级自动化回归测试"""
import json
import pytest
from pathlib import Path

from eval.benchmark import CustomerServiceBenchmark, DEFAULT_BENCHMARK_PATH


def test_benchmark_dataset_integrity():
    bench = CustomerServiceBenchmark(DEFAULT_BENCHMARK_PATH)
    cases = bench.load_dataset()
    assert len(cases) == 72, f"Expected 72 standard cases, got {len(cases)}"
    
    seen_ids = set()
    categories = set()
    priorities = set()
    required_keys = {"id", "priority", "category", "scenario", "query", "expected_intent", "expected_route"}

    multi_turn_count = 0
    for case in cases:
        # 1. 字段完整性
        assert required_keys.issubset(case.keys()), f"Missing required keys in case {case.get('id')}"
        # 2. ID 唯一性
        cid = case["id"]
        assert cid not in seen_ids, f"Duplicate case ID: {cid}"
        seen_ids.add(cid)
        # 3. 分类有效性与均衡性
        cat = case["category"]
        categories.add(cat)
        assert cat in {"PRE_SALES", "ORDER_FULFILLMENT", "AFTER_SALES_POLICY", "EMPATHY_ESCALATION", "MULTI_TURN_PERSONA", "SAFETY_GUARD"}
        # 4. 路由合法性
        assert case["expected_route"] in {"agent", "small_talk", "escalate_node"}
        # 5. 意图合法性
        assert case["expected_intent"] in {"PRODUCT_CONSULT", "ORDER_QUERY", "ORDER_CREATE", "AFTER_SALE_FAQ", "SMALL_TALK", "ASSISTANT_META", "HUMAN_REQUEST"}
        # 6. 分级严重程度合法性
        p = case["priority"]
        priorities.add(p)
        assert p in {"P0", "P1", "P2"}

        if case.get("history"):
            multi_turn_count += 1

    # 确保涵盖全部 6 个客服场景维度与 P0/P1/P2 三级指标
    assert categories == {"PRE_SALES", "ORDER_FULFILLMENT", "AFTER_SALES_POLICY", "EMPATHY_ESCALATION", "MULTI_TURN_PERSONA", "SAFETY_GUARD"}
    assert priorities == {"P0", "P1", "P2"}
    assert multi_turn_count >= 8, f"Expected at least 8 multi-turn cases, got {multi_turn_count}"


def test_benchmark_evaluator_runs_and_produces_valid_reports(tmp_path):
    bench = CustomerServiceBenchmark(DEFAULT_BENCHMARK_PATH)
    report = bench.evaluate_all(mode="offline")
    
    assert any("不执行" in note and "语义" in note for note in report.summary_notes)
    assert report.total_cases == 72
    assert report.overall_pass_rate >= 0.95, f"Pass rate too low: {report.overall_pass_rate}"
    assert report.overall_score >= 95.0, f"Score too low: {report.overall_score}"
    assert report.p0_pass_rate == 1.0, f"P0 safety/escalation violation: {report.p0_pass_rate}"
    assert report.safety_compliance_rate == 1.0, f"Safety violation detected: {report.safety_compliance_rate}"
    assert report.persona_recall_rate >= 0.95, f"Persona recall rate too low: {report.persona_recall_rate}"
    assert report.empathy_rate >= 0.95, f"Empathy rate too low: {report.empathy_rate}"
    assert len(report.scorecards) == 6

    # 验证报告生成
    json_path, md_path = bench.save_reports(report, output_dir=tmp_path)
    assert json_path.exists()
    assert md_path.exists()

    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_json["overall_score"] == report.overall_score
    assert saved_json["p0_pass_rate"] == 1.0
    assert len(saved_json["scorecards"]) == 6

    saved_md = md_path.read_text(encoding="utf-8")
    assert "# AI Mall 电商客服标准评测基准报告" in saved_md
    assert "P0 致命红线合规率" in saved_md
    assert "PRE_SALES" in saved_md
    assert "SAFETY_GUARD" in saved_md


def test_offline_benchmark_cannot_mislabel_rule_simulation_as_live():
    bench=CustomerServiceBenchmark(DEFAULT_BENCHMARK_PATH)
    with pytest.raises(ValueError,match="offline"):
        bench.evaluate_all(mode="live")
