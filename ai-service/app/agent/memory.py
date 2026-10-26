"""长期记忆管理：用户画像与人设提取、Prompt 注入与跨会话持久化"""
import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.clients.backend_client import backend_client
from app.clients.llm import get_intent_llm

logger = logging.getLogger("ai-service.memory")

MEMORY_EXTRACT_SYSTEM_PROMPT = """你是一个长期记忆提取器。分析用户与AI助手的最新一轮对话，提取关于用户的长期事实与画像偏好。
只提取有长期价值的信息，分类如下：
- IDENTITY: 称呼与人设（如用户名字 user_name、助手昵称 assistant_name）
- PREFERENCE: 消费偏好（如 budget 预算、brand 品牌偏好、category 品类偏好、feature 特性偏好）
- FACT: 用户长期背景事实（如 hobby 爱好、pet 宠物、family 家庭、habit 习惯等）

如果本轮对话没有值得长期记忆的信息（如普通问候、单纯查询某订单状态、通用政策咨询），输出空数组 []。
注意：提取出的值要简短准确，不要主观猜测。

只输出严格的 JSON 数组（不要任何 markdown 或额外文字）：
[{"category": "IDENTITY|PREFERENCE|FACT", "key": "键名", "value": "简明记忆值"}]"""


def parse_naming_command(text: str) -> dict[str, str]:
    """快速规则提取用户明确发出的称呼/人设指令，保证本轮对话毫秒级实时生效"""
    if not text:
        return {}
    t = text.strip()
    res: dict[str, str] = {}

    # 1. 双方互定: "你叫大肥鱼，我叫派蒙" 或 "我叫派蒙，你叫大肥鱼"
    m1 = re.search(
        r"(?:你叫|叫你|称呼你为)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,16})"
        r"[，, ；;和且]+(?:我叫|叫我|我是|称呼我为)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,16})",
        t,
    )
    if m1:
        res["assistant_name"] = m1.group(1).strip()
        res["user_name"] = m1.group(2).strip()
        return res

    m2 = re.search(
        r"(?:我叫|叫我|我是|称呼我为)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,16})"
        r"[，, ；;和且]+(?:你叫|叫你|称呼你为)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,16})",
        t,
    )
    if m2:
        res["user_name"] = m2.group(1).strip()
        res["assistant_name"] = m2.group(2).strip()
        return res

    # 2. 单独为助手起名: "从现在开始你叫大肥鱼" / "你叫大肥鱼"
    m3 = re.search(
        r"(?:从现在开始|以后|起)?(?:你叫|叫你|称呼你为)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,16})",
        t,
    )
    if m3 and not any(w in t for w in ["什么", "谁", "吗", "名字", "哪"]):
        res["assistant_name"] = m3.group(1).strip()

    # 3. 单独自我介绍: "我叫派蒙" / "叫我派蒙"
    m4 = re.search(
        r"(?:从现在开始|以后)?(?:我叫|叫我|称呼我为)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,16})",
        t,
    )
    if m4 and not any(w in t for w in ["什么", "谁", "吗", "名字", "买", "要"]):
        res["user_name"] = m4.group(1).strip()

    return res


def format_memory_prompt(user_profile: dict | None, long_term_memory: list[dict] | None = None) -> str:
    """将长期记忆与用户画像格式化为清晰的系统提示词片段"""
    profile = user_profile or {}
    memories = long_term_memory or []

    lines = []
    user_name = profile.get("user_name") or profile.get("nickname")
    if user_name:
        lines.append(f"- 用户称谓：{user_name}（在对话中请自然亲切地称呼对方为「{user_name}」）")

    assistant_name = profile.get("assistant_name")
    if assistant_name:
        lines.append(
            f"- 你的专属昵称：{assistant_name}（这是用户为你起的专属名字；你对外代表「AI Mall」智能电商平台的专业购物助手，专属昵称是「{assistant_name}」）\n"
            f"  * 当用户询问“你是谁”或“你叫什么”时，明确告知你的名字是「{assistant_name}」（或说明自己是 AI Mall 的专属伙伴「{assistant_name}」）；\n"
            f"  * 当用户同时问“你叫什么名字，我叫什么名字”，必须完整回答两个名字：你叫「{assistant_name}」，用户叫「{user_name or '朋友'}」！"
        )

    # 偏好与事实
    pref_lines = []
    for m in memories:
        cat = m.get("category", "")
        k = m.get("key", "")
        v = m.get("value", "")
        if cat in ("PREFERENCE", "FACT") and k and v and k not in ("user_name", "assistant_name"):
            pref_lines.append(f"- {k}: {v}")

    # 同时融合 user_profile 中的其他偏好
    for k, v in profile.items():
        if k not in ("user_name", "assistant_name", "nickname") and v:
            line = f"- {k}: {v}"
            if line not in pref_lines:
                pref_lines.append(line)

    if pref_lines:
        lines.append("## 已知用户偏好与背景记忆：")
        lines.extend(pref_lines)

    if not lines:
        return "（暂无特殊偏好或记忆）"

    return "\n".join(lines)


def format_assistant_greeting(user_profile: dict | None) -> str:
    """生成包含动态人设与用户称谓的快速身份介绍（保持与旧测试的兼容性）"""
    profile = user_profile or {}
    assistant_name = profile.get("assistant_name")
    user_name = profile.get("user_name") or profile.get("nickname")

    prefix = "我是「AI Mall」的 AI 购物助手"
    if assistant_name:
        prefix = f"我是「AI Mall」的 AI 购物助手（也是您的专属伙伴「{assistant_name}」）"

    body = "可以帮您推荐商品、查询订单物流、解答售后退换政策。"

    suffix = "您需要什么帮助？"
    if user_name:
        suffix = f"{user_name}，有什么我可以帮到您的吗？"

    return f"{prefix}，{body}{suffix}"


async def extract_memories_with_llm(user_text: str, ai_text: str) -> list[dict]:
    """使用轻量模型异步提取长期记忆片段"""
    if not user_text or len(user_text.strip()) < 3:
        return []
    llm = get_intent_llm()
    prompt = f"用户说: {user_text}\nAI回复: {ai_text}"
    try:
        resp = await llm.ainvoke([
            SystemMessage(content=MEMORY_EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        content = getattr(resp, "content", "") or ""
        # 提取 JSON 数组
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            items = json.loads(match.group())
            if isinstance(items, list):
                valid = []
                for it in items:
                    if isinstance(it, dict) and it.get("key") and it.get("value"):
                        valid.append({
                            "category": str(it.get("category", "FACT")).upper(),
                            "key": str(it.get("key")).strip(),
                            "value": str(it.get("value")).strip(),
                        })
                return valid
    except Exception as e:
        logger.warning("extract_memories_with_llm failed: %s", e)
    return []


async def background_memory_extraction(user_id: int, user_text: str, ai_text: str):
    """后台任务：结合规则与 LLM 提取记忆，并回写后端数据库持久化"""
    try:
        memories = []
        # 1. 规则提取即时命名指令
        naming = parse_naming_command(user_text)
        if "user_name" in naming:
            memories.append({"category": "IDENTITY", "key": "user_name", "value": naming["user_name"]})
        if "assistant_name" in naming:
            memories.append({"category": "IDENTITY", "key": "assistant_name", "value": naming["assistant_name"]})

        # 2. 如果不是简单的纯命名，尝试用 LLM 提取消费偏好/事实
        if len(user_text) > 6 and not naming:
            llm_memories = await extract_memories_with_llm(user_text, ai_text)
            for m in llm_memories:
                if not any(x["key"] == m["key"] for x in memories):
                    memories.append(m)

        if memories and user_id > 0:
            logger.info("saving extracted memories for user %s: %s", user_id, memories)
            await backend_client.upsert_user_memory(user_id, memories)
    except Exception as e:
        logger.warning("background_memory_extraction failed for user %s: %s", user_id, e)
