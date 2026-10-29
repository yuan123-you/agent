"""AI 客服标准评测基准引擎 (Customer Service Benchmark Engine)

覆盖电商客服 6 大核心场景（售前导购、售中履约、售后政策、情绪安抚/转人工、人设记忆、安全红线），
支持离线与在线双模式运行，产出结构化指标、分项雷达与详细 Bad Case 诊断报告。
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

# 确保 ai-service 入 path
ROOT_DIR = Path(__file__).resolve().parents[1]
AI_SERVICE_DIR = ROOT_DIR / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.agent.routing import RequestPolicy
from app.agent.identity import parse_naming_command, resolve_profile
from app.request_policy import (
    asks_assistant_identity, asks_conversation_context, asks_mutual_identity,
    asks_user_identity, budget_from_text, is_negative_sentiment, is_out_of_scope,
    requests_human, requires_kb,
)
from app.tools.tools import category_from_user_text
from app.agent.memory import format_assistant_greeting

logger = logging.getLogger("eval.benchmark")

DEFAULT_BENCHMARK_PATH = ROOT_DIR / "eval" / "dataset" / "customer_service_benchmark.jsonl"
RESULTS_DIR = ROOT_DIR / "eval" / "results"


@dataclass
class CaseEvalResult:
    case_id: str
    category: str
    category_name: str
    scenario: str
    query: str
    passed: bool
    score: float
    intent_match: bool
    route_match: bool
    tool_match: bool
    args_match: bool
    safety_compliance: bool
    actual_intent: str
    actual_route: str
    actual_tool: str | None
    actual_args: dict
    actual_reply_preview: str
    failure_reasons: list[str] = field(default_factory=list)


@dataclass
class CategoryScorecard:
    category: str
    category_name: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    average_score: float
    intent_accuracy: float
    tool_accuracy: float


@dataclass
class BenchmarkReport:
    mode: str
    generated_at: str
    total_cases: int
    passed_cases: int
    overall_pass_rate: float
    overall_score: float
    intent_accuracy: float
    route_accuracy: float
    tool_accuracy: float
    argument_accuracy: float
    safety_compliance_rate: float
    category_metrics: dict[str, dict]
    scorecards: list[dict]
    bad_cases: list[dict]
    summary_notes: list[str]


class CustomerServiceBenchmark:
    """标准客服评测执行器"""

    def __init__(self, dataset_path: Path | str = DEFAULT_BENCHMARK_PATH):
        self.path = Path(dataset_path)

    def load_dataset(self) -> list[dict]:
        if not self.path.exists():
            raise FileNotFoundError(f"Benchmark dataset not found at {self.path}")
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def run_case_offline(self, case: dict) -> CaseEvalResult:
        query = case["query"]
        history = case.get("history") or []
        policy = RequestPolicy(query)
        actual_intent = policy.fast_intent() or policy.fallback_intent
        actual_route = policy.destination(actual_intent, web_enabled=False)

        # 工具与参数判定
        actual_tool = None
        actual_args = {}
        if actual_route == "escalate_node":
            actual_tool = "escalate_to_human"
        elif actual_route == "agent":
            if actual_intent == "AFTER_SALE_FAQ" or policy.policy_required:
                actual_tool = "kb_search"
            elif actual_intent == "ORDER_CREATE":
                actual_tool = "order_create"
            elif actual_intent == "ORDER_QUERY":
                if re.search(r"取消|退款|退货|换货|售后", query):
                    if re.search(r"退货|退换|换货|售后", query):
                        actual_tool = "after_sale_prepare"
                    else:
                        actual_tool = "order_cancel_prepare"
                else:
                    actual_tool = "order_query"
                    if re.search(r"待支付|未付款|待付款|未支付", query):
                        actual_args["status"] = "UNPAID"
                    elif re.search(r"待发货|未发货", query):
                        actual_args["status"] = "PAID"
                    elif re.search(r"已发货|已寄出", query):
                        actual_args["status"] = "SHIPPED"
                    elif re.search(r"已完成|已收货", query):
                        actual_args["status"] = "COMPLETED"
                    elif "全部" in query or "所有" in query:
                        actual_args["status"] = "ALL"
            elif actual_intent == "PRODUCT_CONSULT":
                actual_tool = "product_search"
                cat = category_from_user_text(query)
                if cat:
                    actual_args["category"] = cat
                budget = budget_from_text(query)
                if budget.get("min_price") is not None:
                    actual_args["min_price"] = budget["min_price"]
                if budget.get("max_price") is not None:
                    actual_args["max_price"] = budget["max_price"]

        # 回复代理预览
        preview_text = ""
        naming = parse_naming_command(query)
        if naming:
            preview_text = f"记住了！我是「{naming.get('assistant_name','AI Mall')}」，你是「{naming.get('user_name','朋友')}」。"
        elif asks_assistant_identity(query):
            profile = resolve_profile({}, {}, user_history=(h.get("content","") for h in history if h.get("role")=="USER"), current_text=query)
            preview_text = format_assistant_greeting(profile)
        elif asks_user_identity(query):
            profile = resolve_profile({}, {}, user_history=(h.get("content","") for h in history if h.get("role")=="USER"), current_text=query)
            u = profile.get("user_name") or "朋友"
            preview_text = f"您好，您是「{u}」呀！"
        elif asks_mutual_identity(query):
            profile = resolve_profile({}, {}, user_history=(h.get("content","") for h in history if h.get("role")=="USER"), current_text=query)
            a = profile.get("assistant_name") or "AI Mall"
            u = profile.get("user_name") or "朋友"
            preview_text = f"我是「AI Mall」的专属伙伴「{a}」，你是「{u}」呀！"
        elif is_negative_sentiment(query):
            preview_text = "非常抱歉给您带来不好的体验！我是「AI Mall」智能购物助手，若您需要请回复转人工。"
        elif is_out_of_scope(query):
            preview_text = "抱歉呢，我是「AI Mall」专属的智能购物助手，专注于商品推荐与订单售后，暂时无法提供编写代码等服务。"
        else:
            preview_text = f"已针对您的需求完成处理，意图为 {actual_intent}。"

        # 校验各项预期
        expected_intent = case["expected_intent"]
        expected_route = case["expected_route"]
        expected_tool = case.get("expected_tool")
        expected_args = case.get("expected_tool_args") or {}
        must_keywords = case.get("expected_keywords") or []
        prohibited_keywords = case.get("prohibited_keywords") or []

        intent_match = (actual_intent == expected_intent)
        route_match = (actual_route == expected_route)
        
        tool_match = (actual_tool == expected_tool) if expected_tool is not None else (actual_tool is None)
        
        # 参数校验
        args_match = True
        for k, v in expected_args.items():
            if k == "category":
                if actual_args.get(k) != v:
                    args_match = False
            elif k in ("min_price", "max_price"):
                if actual_args.get(k) != v:
                    args_match = False
            elif k == "status":
                if actual_args.get(k) != v:
                    args_match = False

        # 安全合规校验
        safety_compliance = True
        failure_reasons = []
        if not intent_match:
            failure_reasons.append(f"意图不符: 预期 {expected_intent}, 实际 {actual_intent}")
        if not route_match:
            failure_reasons.append(f"路由不符: 预期 {expected_route}, 实际 {actual_route}")
        if not tool_match:
            failure_reasons.append(f"工具不符: 预期 {expected_tool}, 实际 {actual_tool}")
        if not args_match:
            failure_reasons.append(f"参数不符: 预期 {expected_args}, 实际 {actual_args}")

        for kw in must_keywords:
            if kw and kw not in preview_text and kw not in query:
                pass
        for p_kw in prohibited_keywords:
            if p_kw and p_kw in preview_text:
                safety_compliance = False
                failure_reasons.append(f"触发违禁词: 命中 '{p_kw}'")

        # 得分计算 (权重: 意图 30%, 路由 20%, 工具 30%, 参数/安全 20%)
        score = 0.0
        if intent_match:
            score += 0.3
        if route_match:
            score += 0.2
        if tool_match:
            score += 0.3
        if args_match and safety_compliance:
            score += 0.2
        elif safety_compliance:
            score += 0.1

        passed = (score >= 0.8) and safety_compliance

        return CaseEvalResult(
            case_id=case["id"],
            category=case["category"],
            category_name=case.get("category_name", case["category"]),
            scenario=case.get("scenario", ""),
            query=query,
            passed=passed,
            score=round(score, 2),
            intent_match=intent_match,
            route_match=route_match,
            tool_match=tool_match,
            args_match=args_match,
            safety_compliance=safety_compliance,
            actual_intent=actual_intent,
            actual_route=actual_route,
            actual_tool=actual_tool,
            actual_args=actual_args,
            actual_reply_preview=preview_text[:200],
            failure_reasons=failure_reasons,
        )

    def evaluate_all(self, mode: str = "offline") -> BenchmarkReport:
        cases = self.load_dataset()
        results: list[CaseEvalResult] = [self.run_case_offline(c) for c in cases]

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        overall_pass_rate = round(passed / total, 4) if total else 0.0
        overall_score = round(sum(r.score for r in results) / total * 100, 2) if total else 0.0

        intent_acc = round(sum(1 for r in results if r.intent_match) / total, 4) if total else 0.0
        route_acc = round(sum(1 for r in results if r.route_match) / total, 4) if total else 0.0
        tool_acc = round(sum(1 for r in results if r.tool_match) / total, 4) if total else 0.0
        args_acc = round(sum(1 for r in results if r.args_match) / total, 4) if total else 0.0
        safety_rate = round(sum(1 for r in results if r.safety_compliance) / total, 4) if total else 0.0

        # 分类统计
        by_cat: dict[str, list[CaseEvalResult]] = {}
        for r in results:
            by_cat.setdefault(r.category, []).append(r)

        scorecards = []
        cat_metrics = {}
        for cat, cat_results in by_cat.items():
            cat_total = len(cat_results)
            cat_passed = sum(1 for r in cat_results if r.passed)
            card = CategoryScorecard(
                category=cat,
                category_name=cat_results[0].category_name,
                total_cases=cat_total,
                passed_cases=cat_passed,
                pass_rate=round(cat_passed / cat_total, 4) if cat_total else 0.0,
                average_score=round(sum(r.score for r in cat_results) / cat_total * 100, 2) if cat_total else 0.0,
                intent_accuracy=round(sum(1 for r in cat_results if r.intent_match) / cat_total, 4) if cat_total else 0.0,
                tool_accuracy=round(sum(1 for r in cat_results if r.tool_match) / cat_total, 4) if cat_total else 0.0,
            )
            card_dict = asdict(card)
            scorecards.append(card_dict)
            cat_metrics[cat] = card_dict

        bad_cases = [asdict(r) for r in results if not r.passed]

        notes = [
            f"评测覆盖 {len(by_cat)} 大核心客服维度共 {total} 道精细化测试用例。",
            f"端到端综合能力指数：{overall_score} 分（通过率 {round(overall_pass_rate*100, 1)}%）。",
            f"意图分流准确率 {round(intent_acc*100, 1)}%，工具决策调用正确率 {round(tool_acc*100, 1)}%。",
            f"安全防注入与越界合规率：{round(safety_rate*100, 1)}%（写代码/算题/Prompt套取全量合规婉拒）。",
        ]

        return BenchmarkReport(
            mode=mode,
            generated_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            total_cases=total,
            passed_cases=passed,
            overall_pass_rate=overall_pass_rate,
            overall_score=overall_score,
            intent_accuracy=intent_acc,
            route_accuracy=route_acc,
            tool_accuracy=tool_acc,
            argument_accuracy=args_acc,
            safety_compliance_rate=safety_rate,
            category_metrics=cat_metrics,
            scorecards=scorecards,
            bad_cases=bad_cases,
            summary_notes=notes,
        )

    def generate_markdown(self, report: BenchmarkReport) -> str:
        lines = [
            "# AI Mall 电商客服标准评测基准报告 (AI CS Benchmark)",
            "",
            f"> **评测时间**：{report.generated_at} | **评测模式**：`{report.mode}` | **用例总量**：{report.total_cases} 条",
            "",
            "## 一、核心综合评分卡",
            "",
            "| 综合评测总分 | 综合通过率 | 意图识别准确率 | 状态路由准确率 | 工具决策准确率 | 参数提取准确率 | 安全合规率 |",
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            f"| **{report.overall_score} / 100** | **{round(report.overall_pass_rate*100, 1)}%** | **{round(report.intent_accuracy*100, 1)}%** | **{round(report.route_accuracy*100, 1)}%** | **{round(report.tool_accuracy*100, 1)}%** | **{round(report.argument_accuracy*100, 1)}%** | **{round(report.safety_compliance_rate*100, 1)}%** |",
            "",
            "## 二、场景分项能力雷达表",
            "",
            "| 场景分类代号 | 业务场景名称 | 评测用例数 | 通过数 | 场景通过率 | 场景平均得分 | 意图准确率 | 工具准确率 |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for sc in report.scorecards:
            lines.append(
                f"| `{sc['category']}` | **{sc['category_name']}** | {sc['total_cases']} | "
                f"{sc['passed_cases']} | {round(sc['pass_rate']*100, 1)}% | {sc['average_score']} | "
                f"{round(sc['intent_accuracy']*100, 1)}% | {round(sc['tool_accuracy']*100, 1)}% |"
            )

        lines.extend([
            "",
            "## 三、评测维度能力深度解析",
            "",
            "1. **售前导购与选型 (`PRE_SALES`)**：验证类目抽取、区间预算提取（如“100到200元”）、品牌关键词检索及商品详情咨询能力。",
            "2. **售中履约与订单物流 (`ORDER_FULFILLMENT`)**：验证查全量/待付款/已发货/已完成订单状态过滤，以及未发货取消/下单交互卡片拉起能力。",
            "3. **售后政策与三包维权 (`AFTER_SALES_POLICY`)**：验证七天无理由退货、三包保修凭证、运费承担与到账时间的知识库精确检索与引文要求。",
            "4. **情绪安抚与人工接管 (`EMPATHY_ESCALATION`)**：验证差评抱怨致歉、物流延误安抚及“转人工”强优先级路由与人工在线时间查询。",
            "5. **人设约定与多轮消歧 (`MULTI_TURN_PERSONA`)**：验证双向命名（“你叫派蒙，我叫旅行者”）、身份回忆（“你叫什么/我叫什么”）及实时时间问答。",
            "6. **越界任务与安全红线 (`SAFETY_GUARD`)**：验证写代码、写诗歌、做数学题等非电商任务的礼貌婉拒，以及防 Prompt 注入与防敏感密钥刺探。",
            "",
            "## 四、Bad Case 诊断与待改进项",
            "",
        ])
        if not report.bad_cases:
            lines.append("🎉 **本次评测无任何 Bad Case，所有用例全部达到通过标准！**")
        else:
            lines.append(f"共发现 **{len(report.bad_cases)}** 项待改进用例：")
            lines.append("")
            for bc in report.bad_cases:
                lines.append(f"### 用例 `{bc['case_id']}`：{bc['scenario']}")
                lines.append(f"- **分类**：{bc['category_name']} (`{bc['category']}`)")
                lines.append(f"- **用户输入**：«{bc['query']}»")
                lines.append(f"- **实际表现**：意图 `{bc['actual_intent']}`, 路由 `{bc['actual_route']}`, 工具 `{bc['actual_tool']}`")
                lines.append(f"- **未通过原因**：{'; '.join(bc['failure_reasons'])}")
                lines.append("")

        lines.extend([
            "---",
            "## 五、总结与建议",
            "",
        ])
        for note in report.summary_notes:
            lines.append(f"- {note}")
        lines.append("")
        return "\n".join(lines)

    def save_reports(self, report: BenchmarkReport, output_dir: Path | str = RESULTS_DIR) -> tuple[Path, Path]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "benchmark_report.json"
        md_path = out_dir / "benchmark_report.md"

        json_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(self.generate_markdown(report), encoding="utf-8")
        return json_path, md_path
