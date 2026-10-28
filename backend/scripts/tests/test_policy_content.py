"""Offline SPEC-01 contracts for the FAQ seed and its generated knowledge corpus."""
import json
import re
from pathlib import Path

import pytest

from backend.scripts.kb_dataset import build_dataset, write_dataset

ROOT = Path(__file__).resolve().parents[3]
SEEDS = ROOT / "backend/src/main/resources/kbseed"


def canonical_faqs():
    # Same multiline item format and first-answer-wins semantics as FaqService.
    answers = {}
    for match in re.finditer(r"\*\*(.+?[？?])\*\*\s*(.+)$", (SEEDS / "platform-policies.md").read_text(encoding="utf-8"), re.MULTILINE):
        answers.setdefault(match[1].strip(), match[2].strip())
    return answers


@pytest.mark.parametrize("question,required", [
    ("商家一直不处理售后怎么办？", ("人工", "不会", "平台")),
    ("退款多久能到账？", ("SIMULATED", "SIM-", "人工", "不代表真实资金到账")),
    ("可以只退款不退货吗？", ("已支付未发货", "人工审核", "不等于退款")),
    ("换货能改成别的型号或 SKU 吗？", ("原商品", "原 SKU", "不支持跨商品", "不支持跨 SKU", "补退差价")),
    ("7天无理由从哪天开始算？", ("适用条件", "人工", "不配置统一七天")),
    ("商品拆封了还能7天无理由退货吗？", ("适用条件", "质量问题")),
    ("使用过的商品可以退货吗？", ("适用条件", "质量问题")),
    ("生鲜食品收到坏了怎么办？", ("尽快", "人工", "模拟退款")),
    ("退货运费谁承担？", ("责任", "不代表", "报销")),
    ("收到货少件/错发怎么办？", ("人工", "模拟退款", "原 SKU")),
    ("可以取消已发货的订单吗？", ("人工", "模拟退款", "不能直接取消")),
    ("显示签收但我没收到货怎么办？", ("人工", "模拟退款")),
    ("外包装破损可以拒收吗？", ("人工", "模拟退款")),
    ("商家卖假货怎么投诉？", ("人工", "模拟退款", "赔偿")),
    ("平台有运费险、上门取件或加急退款吗？", ("不承诺", "运费险", "上门取件", "加急", "模拟")),
])
def test_faq_answers_explain_executable_demo_boundary(question, required):
    answer = canonical_faqs().get(question, "")
    for fragment in required:
        assert fragment in answer, f"{question}: missing {fragment!r} in {answer!r}"


OBSOLETE_PROMISES = (
    "系统自动同意", "系统会自动同意", "超时系统自动同意",
    "真实渠道一般", "真实渠道微信/支付宝", "退款原路退回", "按原支付路径退回",
    "取消订单即全额退款", "客服确认商家尚未发货后关闭订单",
    "更换等价其他型号", "更换高价型号需补差价", "更换低价型号退还差价",
    "第一个自然日为签收当日", "签收日是第一天", "物流签收当日为第1天",
    "七日从物流签收当日开始", "签收之日起7自然日内", "签收之日起15自然日内",
    "用户自物流签收之日起七个自然日内提交申请", "签收之日起十五个自然日内出现",
    "七天无理由和十五天质量换货均从物流签收当日开始计算",
)


@pytest.mark.parametrize("source", ["canonical", "generated", "rebuilt"])
def test_policy_sources_do_not_reintroduce_unsupported_promises(source):
    if source == "canonical":
        documents = [("platform-policies", (SEEDS / "platform-policies.md").read_text(encoding="utf-8"))]
    elif source == "generated":
        documents = [(path.stem, path.read_text(encoding="utf-8")) for path in sorted((SEEDS / "generated/docs").glob("*.md"))]
    else:
        documents = [(doc.key, doc.content) for doc in build_dataset()]
    violations = [(key, phrase) for key, content in documents for phrase in OBSOLETE_PROMISES if phrase in content]
    assert not violations, violations


def test_each_retrievable_policy_explains_simulated_human_review_and_exchange_limits():
    documents = [("platform-policies", (SEEDS / "platform-policies.md").read_text(encoding="utf-8"))]
    documents += [(doc.key, doc.content) for doc in build_dataset()]
    for key, content in documents:
        for fragment in ("模拟支付", "SIMULATED", "SIM-", "人工审核", "WAITING_REFUND", "原商品", "原 SKU", "不支持跨商品", "不支持跨 SKU", "不会因超时自动同意", "运费险", "加急"):
            assert fragment in content, f"{key}: missing {fragment!r}"


def test_conditional_consumer_rights_survive_without_an_invented_deadline():
    contents = [(SEEDS / "platform-policies.md").read_text(encoding="utf-8")]
    contents += [doc.content for doc in build_dataset() if doc.key == "seven-day-return"]
    for content in contents:
        for fragment in ("七天无理由", "适用条件", "法律", "商品完好", "质量问题", "不配置统一七天"):
            assert fragment in content
    assert "网络购买商品七日无理由退货暂行办法" in contents[0]


def test_committed_seed_documents_and_manifest_match_offline_regeneration(tmp_path):
    output = tmp_path / "generated"
    write_dataset(output, tmp_path / "eval.jsonl")
    expected_files = sorted(path.relative_to(output) for path in output.rglob("*") if path.is_file())
    committed_files = sorted(path.relative_to(SEEDS / "generated") for path in (SEEDS / "generated").rglob("*") if path.is_file())
    assert committed_files == expected_files
    for relative in expected_files:
        assert (SEEDS / "generated" / relative).read_text(encoding="utf-8") == (output / relative).read_text(encoding="utf-8"), str(relative)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["documents"]:
        assert entry["charCount"] == len((SEEDS.parent / entry["resource"]).read_text(encoding="utf-8"))
