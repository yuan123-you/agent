"""健康检查：
- /health/live      存活探针（进程活着即 200）
- /health           综合状态：status=UP/DEGRADED + 各依赖 + 降级列表
- /health/ready     就绪探针（LLM / Milvus / 后端全部可用才 200，否则 503 + 降级列表）
- /health/degraded  降级依赖列表
依赖状态由 main.lifespan 在启动时登记缓存（Milvus），也可在请求时实时探测（LLM/后端/Milvus）。
"""
import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, Response

from app import rag as _rag
from app.config import settings
from app.resilience import budget_scope, run
from app.rag.vectorstore import _milvus_sync

router = APIRouter()
logger = logging.getLogger("ai-service.health")
_HEALTH_TIMEOUT_S = 3.0

# 运行时依赖状态（main.lifespan 显式初始化时登记；name -> 降级原因，空列表即全部就绪）
_degrade_reasons: dict[str, str] = {}


def set_dependency(name: str, ok: bool, detail: str = "") -> None:
    """登记/更新某依赖的就绪状态：ok=True 清除降级标记，否则记录原因。"""
    if ok:
        _degrade_reasons.pop(name, None)
    else:
        _degrade_reasons[name] = detail or f"{name} unavailable"


def degraded_list() -> list[str]:
    return sorted(_degrade_reasons.keys())


async def _check_milvus() -> bool:
    try:
        async def attempt(timeout):
            def probe():
                return _milvus_sync(_rag.vectorstore.get_vectorstore().client,"list_collections",timeout_s=timeout)
            return await asyncio.to_thread(probe)
        await run("health.milvus",attempt,replay_safe=True,max_attempts=1,attempt_timeout_s=_HEALTH_TIMEOUT_S)
        return True
    except Exception as e:
        logger.warning("milvus health check failed: %s", e)
        set_dependency("milvus", False, str(e)[:200])
        return False


async def _check_llm() -> bool:
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_S,trust_env=False) as client:
            async def attempt(timeout):
                return await client.get(f"{settings.llm_api_base.rstrip('/')}/models",timeout=timeout,
                                        headers={"Authorization": f"Bearer {settings.llm_api_key}"})
            r = await run("health.model",attempt,replay_safe=True,max_attempts=1,attempt_timeout_s=_HEALTH_TIMEOUT_S)
            return r.status_code < 400
    except Exception as e:
        logger.warning("llm health check failed: %s", e)
        set_dependency("llm", False, str(e)[:200])
        return False


async def _check_backend() -> bool:
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_S,trust_env=False) as client:
            async def attempt(timeout):
                return await client.get(f"{settings.backend_base_url.rstrip('/')}/actuator/health",timeout=timeout)
            r = await run("health.backend",attempt,replay_safe=True,max_attempts=1,attempt_timeout_s=_HEALTH_TIMEOUT_S)
            return r.status_code < 400 and r.json().get("status") == "UP"
    except Exception as e:
        logger.warning("backend health check failed: %s", e)
        set_dependency("backend", False, str(e)[:200])
        return False


async def _probe_all() -> dict[str, bool]:
    statuses={name:False for name in ("milvus","llm","backend")}
    async def probe(name,check):
        statuses[name]=await check()
    with budget_scope(_HEALTH_TIMEOUT_S,retry_tokens=0,inherit=False):
        try:
            async with asyncio.timeout(_HEALTH_TIMEOUT_S):
                await asyncio.gather(probe("milvus",_check_milvus),probe("llm",_check_llm),probe("backend",_check_backend))
        except TimeoutError:
            logger.warning("health probe total deadline exhausted")
    return statuses


@router.get("/health/live")
async def live():
    """存活探针：进程活着即 200，不做外部依赖探测。"""
    return {"status": "UP"}


@router.get("/health")
async def health():
    """综合状态：是否可用 + 各依赖状态 + 降级列表（服务降级时仍返回 200，可服务但部分功能失效）。"""
    statuses = await _probe_all()
    degraded = [k for k, ok in statuses.items() if not ok]
    return {
        "status": "UP" if not degraded else "DEGRADED",
        "dependencies": statuses,
        "degraded": degraded,
    }


@router.get("/health/ready")
async def ready():
    """就绪探针：LLM / Milvus / 后端全部可用才 200；否则 503 + 降级依赖列表。"""
    statuses = await _probe_all()
    degraded = [k for k, ok in statuses.items() if not ok]
    payload = {
        "status": "UP" if not degraded else "DEGRADED",
        "dependencies": statuses,
        "degraded": degraded,
    }
    if degraded:
        return Response(status_code=503, content=json.dumps(payload),
                        media_type="application/json")
    return payload


@router.get("/health/degraded")
async def degraded():
    """降级依赖列表：无降级时返回空列表。"""
    statuses = await _probe_all()
    reasons = {
        k: (_degrade_reasons.get(k) or f"{k} unavailable")
        for k, ok in statuses.items() if not ok
    }
    return {"degraded": list(reasons.keys()), "reasons": reasons}