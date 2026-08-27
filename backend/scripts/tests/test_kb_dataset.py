import hashlib
import json
from pathlib import Path

from backend.scripts.kb_dataset import build_dataset, write_dataset


EXPECTED_TOPICS = {
    "平台与账户",
    "订单管理",
    "支付与退款",
    "发票服务",
    "会员与优惠",
    "普通物流",
    "特殊物流",
    "跨境与偏远配送",
    "无理由退货",
    "质量问题与换货",
    "质保与维修",
    "投诉与平台介入",
    "账户安全与隐私",
    "数码家电与个护",
    "食品母婴与家居",
}
FORBIDDEN_MARKERS = ("合成测试", "KB-", "｜场景", "精确编号")
OLD_CHAR_COUNTS = {
    "platform-account-service": 1157,
    "order-change-cancel": 1108,
    "standard-delivery": 1089,
    "special-delivery": 1039,
    "crossborder-remote-delivery": 1064,
    "seven-day-return": 1087,
    "quality-exchange": 1133,
    "warranty-repair": 1103,
    "invoice-service": 1108,
    "membership-promotions": 1095,
    "payment-refund": 1106,
    "complaint-mediation": 1110,
    "account-security-privacy": 1108,
    "digital-home-beauty-aftercare": 1144,
    "food-family-home-aftercare": 1220,
}
REQUIRED_SECTIONS = (
    "## 文档控制与使用说明",
    "## 术语与状态定义",
    "## 角色职责与协作边界",
    "## 端到端业务流程",
    "## 异常场景处置手册",
    "## 凭证、记录与数据要求",
    "## 服务时限与升级机制",
    "## 质量检查与运营审计",
    "## 业务案例",
    "## 常见问题",
)


def _digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_build_dataset_contains_formal_service_documents():
    docs = build_dataset()

    assert len(docs) == 15
    assert {doc.topic for doc in docs} == EXPECTED_TOPICS
    assert {doc.file_format for doc in docs} == {"MD"}
    assert len({doc.key for doc in docs}) == len(docs)
    assert len({doc.title for doc in docs}) == len(docs)
    assert all(doc.resource.endswith(f"{doc.key}.md") for doc in docs)
    assert all(doc.title.startswith("AI Mall ") for doc in docs)
    assert {doc.doc_type for doc in docs} == {"FAQ", "INTRO", "POLICY"}
    assert all(len(doc.content) >= max(11_000, OLD_CHAR_COUNTS[doc.key] * 10) for doc in docs)
    assert all(doc.content.count("## ") >= 12 for doc in docs)
    assert all(all(section in doc.content for section in REQUIRED_SECTIONS) for doc in docs)
    assert all("## 核心规则" in doc.content for doc in docs)
    assert all(not any(marker in doc.title + doc.content for marker in FORBIDDEN_MARKERS) for doc in docs)


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
        content = path.read_text(encoding="utf-8")
        assert item["charCount"] == len(content)
        assert item["charCount"] >= max(11_000, OLD_CHAR_COUNTS[item["key"]] * 10)
        assert item["estimatedChunkCount"] > 0
        assert item["fileFormat"] == "MD"


def test_write_dataset_removes_stale_generated_documents(tmp_path):
    output = tmp_path / "corpus"
    stale = output / "docs" / "synthetic-kb-999.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    write_dataset(output, tmp_path / "eval.jsonl")

    assert not stale.exists()
    assert len(list((output / "docs").iterdir())) == 15


def test_eval_rows_are_natural_questions_grounded_in_document_content(tmp_path):
    output = tmp_path / "corpus"
    eval_path = tmp_path / "eval.jsonl"
    write_dataset(output, eval_path)
    docs_by_key = {doc.key: doc for doc in build_dataset()}
    rows = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines()]

    assert len(rows) == 15
    assert {row["difficulty"] for row in rows} == {
        "direct", "paraphrase", "conditional", "multi_hop", "temporal", "hard_negative"
    }
    assert all(row["query"].endswith(("？", "?")) for row in rows)
    assert all(not any(marker in row["query"] for marker in FORBIDDEN_MARKERS) for row in rows)
    assert all(row["expected_doc_key"] and row["must_hit"] for row in rows)
    assert all(
        all(expected in docs_by_key[row["expected_doc_key"]].content for expected in row["must_hit"])
        for row in rows
    )
