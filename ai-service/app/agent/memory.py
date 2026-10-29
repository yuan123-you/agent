"""长期记忆管理：用户画像与人设提取、Prompt 注入与跨会话持久化"""
import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.observability.execution_trace import trace_span
from app.agent.identity import IDENTITY_KEYS, normalize_profile, parse_naming_command
from app.agent.prompt_context import compact_prompt_messages
from app.clients.backend_client import backend_client
from app.clients.llm import get_intent_llm

logger = logging.getLogger("ai-service.memory")

MEMORY_EXTRACT_SYSTEM_PROMPT = """你是一个长期记忆提取器。分析用户与AI助手的最新一轮对话，提取关于用户的长期事实与画像偏好。
只提取有长期价值的信息，分类如下：
- PREFERENCE: 消费偏好（如 budget 预算、brand 品牌偏好、category 品类偏好、feature 特性偏好）
- FACT: 用户长期背景事实（如 hobby 爱好、pet 宠物、family 家庭、habit 习惯等）

如果本轮对话没有值得长期记忆的信息（如普通问候、单纯查询某订单状态、通用政策咨询），输出空数组 []。
注意：只提取用户自己明确表达的偏好或事实，不要从 AI 回复推测。称呼由独立的显式命名规则处理，不要提取 user_name、assistant_name 或 IDENTITY。

只输出严格的 JSON 数组（不要任何 markdown 或额外文字）：
[{"category": "PREFERENCE|FACT", "key": "键名", "value": "简明记忆值"}]"""


def format_memory_prompt(user_profile: dict | None, long_term_memory: list[dict] | None = None) -> str:
    """将长期记忆与用户画像格式化为清晰的系统提示词片段"""
    profile = normalize_profile(user_profile)
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
    profile = normalize_profile(user_profile)
    assistant_name = (profile.get("assistant_name") or "").strip()
    user_name = (profile.get("user_name") or profile.get("nickname") or "").strip()

    prefix = "我是「AI Mall」的 AI 购物助手"
    if assistant_name and assistant_name.casefold() != "ai mall":
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
    llm = get_intent_llm(classification=False)
    ai_context = compact_prompt_messages([AIMessage(content=ai_text)], question=user_text)[0].content
    prompt = f"用户说: {user_text}\nAI回复: {ai_context}"
    try:
        with trace_span("memory.extract", kind="model", input={"user":user_text}, model=getattr(llm, "model_name", None)) as span:
            resp = await llm.ainvoke([
                SystemMessage(content=MEMORY_EXTRACT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            span.complete({"content":getattr(resp, "content", ""), "usage":getattr(resp, "usage_metadata", None)})
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


async def persist_naming_memory(user_id: int, user_text: str) -> bool | None:
    """Commit explicit identity before done; None means this is not a naming turn.

    Failure does not destroy the checkpoint/session answer, but is not reported
    as a successful durable cross-session write either.
    """
    naming = parse_naming_command(user_text)
    if not naming:
        return None
    if user_id <= 0:
        return False
    memories = [{"category": "IDENTITY", "key": key, "value": value}
                for key, value in naming.items()]
    try:
        with trace_span("memory.persist_identity", kind="memory", input={"memories":memories}) as span:
            result = await backend_client.upsert_user_memory(user_id, memories)
            span.complete(result, status="FAILED" if "error" in result else "SUCCESS")
        if "error" not in result:
            return True
        logger.warning("identity persistence unavailable for user %s", user_id)
    except Exception:
        logger.warning("identity persistence failed for user %s", user_id, exc_info=True)
    return False


def should_extract_memory(user_text: str) -> bool:
    """Conservative admission for optional inference, not an alternate fact parser.

    Queries/orders do not need a second model call. Values are still extracted
    by the LLM, and identity keys are rejected independently after extraction.
    """
    if re.search(r"[?？]|吗[。！!\s]*$", user_text):
        return False
    return bool(re.search(
        r"我(?:更|比较|一直|平时|通常|特别|最)?(?:喜欢|偏好|习惯|不喜欢|讨厌|养了|家里|家有)"
        r"|我的(?:预算|尺码|职业|工作|爱好)|预算(?:是|为|大概|大约|在|[：:\d])",
        user_text,
    ))


async def background_memory_extraction(user_id: int, user_text: str, ai_text: str):
    """Best-effort preference/fact extraction, owned by the streaming response."""
    if user_id <= 0:
        return
    try:
        if await persist_naming_memory(user_id, user_text) is not None:
            return
        if not should_extract_memory(user_text):
            return
        # Inference cannot overwrite explicit identity, even under a FACT key.
        memories = [item for item in await extract_memories_with_llm(user_text, ai_text)
                    if item.get("key") not in IDENTITY_KEYS
                    and item.get("category") in {"PREFERENCE", "FACT"}]
        if memories:
            with trace_span("memory.persist_preferences", kind="memory", input={"memories":memories}) as span:
                result = await backend_client.upsert_user_memory(user_id, memories)
                span.complete(result, status="FAILED" if "error" in result else "SUCCESS")
            if "error" in result:
                logger.warning("preference persistence unavailable for user %s", user_id)
    except Exception:
        logger.warning("background memory extraction failed for user %s", user_id, exc_info=True)
