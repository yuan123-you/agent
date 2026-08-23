"""Deterministic synthetic ecommerce knowledge corpus builder."""
from __future__ import annotations

import json
import math
import random
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path

SEED = 20260823
DOCUMENT_COUNT = 15
SOURCE_DOCUMENT_COUNT = 300
DOMAINS = [
    "平台基础规则", "订单取消与修改", "支付失败与退款", "电子发票", "会员等级", "优惠券与价保",
    "普通快递", "同城即时配送", "跨境物流", "生鲜冷链", "大件预约配送", "偏远地区配送",
    "七天无理由", "质量问题换货", "质保维修", "投诉与平台介入", "账户安全", "隐私与风控",
    "手机数码", "电脑办公", "家用电器", "服饰内衣", "美妆个护", "食品生鲜", "母婴玩具",
    "运动户外", "图书文娱", "家具家居", "珠宝饰品", "汽车用品",
]
REGIONS = ["全国", "华东", "华南", "华北", "西南", "东北"]
CHANNELS = ["平台自营", "品牌旗舰店", "第三方商家", "跨境专营", "同城门店"]
DIFFICULTIES = ["direct", "paraphrase", "conditional", "multi_hop", "temporal_region", "hard_negative"]


@dataclass(frozen=True)
class DocumentSpec:
    key: str
    title: str
    doc_type: str
    file_format: str
    resource: str
    topic: str
    eval_tags: tuple[str, ...]
    content: str
    estimated_chunks: int

    @property
    def char_count(self) -> int:
        return len(self.content)


def _doc_type(index: int) -> str:
    return "FAQ" if index < 120 else "INTRO" if index < 220 else "POLICY"


def _file_format(index: int) -> str:
    return "MD" if index < 240 else "TXT" if index < 290 else "PDF"


def _section(topic: str, variant: int, section: int, rng: random.Random, markdown: bool) -> str:
    region = REGIONS[(variant + section) % len(REGIONS)]
    channel = CHANNELS[(variant * 2 + section) % len(CHANNELS)]
    days = 1 + (variant * 3 + section * 2) % 30
    amount = 50 + ((variant + 1) * (section + 3) * 17) % 1950
    code = f"KB-{DOMAINS.index(topic)+1:02d}-{variant+1:02d}-{section+1:02d}"
    heading = f"## {section + 1}. {topic}场景 {code}" if markdown else f"[{section + 1}] {topic}场景 {code}"
    exception = ["定制商品", "激活后的数字内容", "已拆封卫生用品", "超过举证时限", "地址信息不完整"][section % 5]
    proof = ["订单截图", "物流面单", "开箱视频", "检测报告", "支付流水"][variant % 5]
    paragraphs = [
        f"适用范围：本条适用于{region}区域的{channel}订单。用户提问可能使用“怎么办”“能不能退”“多久到账”等口语表达；检索时应以编号 {code}、区域、渠道和订单状态共同判断，不能只凭单一关键词作答。",
        f"核心事实：满足页面已标记服务、订单金额不少于{amount}元且在事件发生后{days}个自然日内申请时，可进入标准处理流程。先核验账号与订单，再核验商品状态，最后确认责任方；三个条件缺一不可。",
        f"操作步骤：第一步在订单详情提交申请；第二步上传{proof}并选择原因；第三步等待商家在{1 + section % 5}个工作日内响应；逾期未响应时平台自动提醒，仍无结果可申请平台介入。处理编号为 {code}。",
        f"例外与边界：{exception}默认不适用本条，但若页面另有明确承诺或经检测确认属于非人为质量问题，则按承诺或质量保障规则处理。促销降价、主观不喜欢和质量缺陷是不同原因，不得混为一谈。",
        f"相似规则辨析：{region}与{REGIONS[(variant + section + 1) % len(REGIONS)]}的时效不同，{channel}与{CHANNELS[(variant * 2 + section + 1) % len(CHANNELS)]}的责任主体也不同。出现冲突时，优先采用与订单渠道、地区、有效期完全匹配且版本更新的条款。",
        f"客服答复要点：先复述用户条件，再说明是否满足{days}日期限和{amount}元门槛，列出所需{proof}，最后给出下一步。禁止承诺即时到账或跳过审核；信息不足时应追问地区、渠道、签收日期和商品状态。",
    ]
    return heading + "\n\n" + "\n\n".join(paragraphs)


def _content(index: int, rng: random.Random) -> str:
    topic = DOMAINS[index // 10]
    variant = index % 10
    markdown = _file_format(index) == "MD"
    title = f"AI Mall 合成测试知识库 {index + 1:03d}｜{topic}｜场景{variant + 1}"
    intro = (
        f"# {title}\n\n> 仅用于 Agent + RAG 压力与召回测试，不代表真实平台承诺。"
        if markdown else
        f"{title}\n仅用于 Agent + RAG 压力与召回测试，不代表真实平台承诺。"
    )
    sections = [_section(topic, variant, section, rng, markdown) for section in range(36)]
    return intro + "\n\n" + "\n\n".join(sections) + "\n"


def _selected_source_indexes(count: int = DOCUMENT_COUNT) -> list[int]:
    """Evenly sample the full catalog so reduced corpora retain type/topic/format diversity."""
    if count < 2 or count > SOURCE_DOCUMENT_COUNT:
        raise ValueError(f"count must be between 2 and {SOURCE_DOCUMENT_COUNT}")
    return [slot * (SOURCE_DOCUMENT_COUNT - 1) // (count - 1) for slot in range(count)]


def build_dataset(seed: int = SEED) -> list[DocumentSpec]:
    rng = random.Random(seed)
    docs = []
    for index in _selected_source_indexes():
        topic = DOMAINS[index // 10]
        variant = index % 10
        key = f"synthetic-kb-{index + 1:03d}"
        fmt = _file_format(index)
        ext = fmt.lower()
        title = f"AI Mall 合成测试知识库 {index + 1:03d}｜{topic}｜场景{variant + 1}"
        content = _content(index, rng)
        docs.append(DocumentSpec(
            key=key,
            title=title,
            doc_type=_doc_type(index),
            file_format=fmt,
            resource=f"kbseed/generated/docs/{key}.{ext}",
            topic=topic,
            eval_tags=(REGIONS[variant % len(REGIONS)], CHANNELS[variant % len(CHANNELS)], DIFFICULTIES[index % 6]),
            content=content,
            estimated_chunks=math.ceil(len(content) / (600 - 90)),
        ))
    return docs


def _pdf_bytes(text: str) -> bytes:
    """Create a dependency-free, extractable ASCII PDF for parser coverage."""
    ascii_text = text.encode("ascii", "replace").decode("ascii")
    lines = []
    for raw in ascii_text.splitlines():
        lines.extend(textwrap.wrap(raw, width=88) or [""])
    pages = [lines[i:i + 60] for i in range(0, len(lines), 60)]
    objects: list[bytes] = []
    page_ids = [4 + i * 2 for i in range(len(pages))]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    for page_index, page_lines in enumerate(pages):
        page_id = page_ids[page_index]
        content_id = page_id + 1
        page = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        commands = ["BT /F1 8 Tf 30 810 Td 10 TL"]
        for line in page_lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj T*")
        commands.append("ET")
        stream = "\n".join(commands).encode()
        objects.append(page.encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    output = bytearray(b"%PDF-1.4\n%synthetic\n")
    offsets = [0]
    for object_id, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def _eval_row(doc: DocumentSpec, index: int) -> dict:
    difficulty = DIFFICULTIES[index % len(DIFFICULTIES)]
    region, channel, _ = doc.eval_tags
    source_index = int(doc.key.rsplit("-", 1)[1]) - 1
    code = f"KB-{DOMAINS.index(doc.topic)+1:02d}-{source_index % 10 + 1:02d}-{source_index % 36 + 1:02d}"
    queries = {
        "direct": f"{doc.topic}的处理编号 {code} 适用于什么范围？",
        "paraphrase": f"我在{region}的{channel}订单出问题了，这种情况咋办？",
        "conditional": f"{doc.topic}如果属于例外商品但检测为质量问题还能处理吗？",
        "multi_hop": f"{doc.topic}需要什么凭证，商家逾期后下一步是什么？",
        "temporal_region": f"{region}区域{doc.topic}的期限和相邻区域一样吗？",
        "hard_negative": f"不要返回相似渠道，请查{channel}的{doc.topic}规则 {code}",
    }
    query = queries[difficulty] + (f" 精确编号 {code}" if doc.file_format == "PDF" else "")
    return {
        "query": query,
        "expected_doc_key": doc.key,
        "must_hit": [code, doc.topic],
        "doc_type": doc.doc_type,
        "difficulty": difficulty,
        "note": "合成大规模知识库召回用例",
    }


def write_dataset(output_root: Path, eval_path: Path, seed: int = SEED) -> dict:
    docs = build_dataset(seed)
    docs_dir = output_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    manifest_docs = []
    for doc in docs:
        target = docs_dir / Path(doc.resource).name
        if doc.file_format == "PDF":
            target.write_bytes(_pdf_bytes(doc.content))
        else:
            target.write_text(doc.content, encoding="utf-8", newline="\n")
        manifest_docs.append({
            "key": doc.key, "title": doc.title, "docType": doc.doc_type,
            "fileFormat": doc.file_format, "resource": doc.resource, "topic": doc.topic,
            "evalTags": list(doc.eval_tags), "charCount": doc.char_count,
            "estimatedChunkCount": doc.estimated_chunks,
        })
    manifest = {
        "version": 1,
        "generatedAt": "2026-08-23T00:00:00+08:00",
        "seed": seed,
        "documents": manifest_docs,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text("".join(json.dumps(_eval_row(doc, i), ensure_ascii=False) + "\n" for i, doc in enumerate(docs)), encoding="utf-8")
    return {
        "documents": len(docs),
        "characters": sum(doc.char_count for doc in docs),
        "estimatedChunks": sum(doc.estimated_chunks for doc in docs),
    }


