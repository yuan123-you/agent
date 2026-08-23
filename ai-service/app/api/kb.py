"""知识库接口：文档摄取（异步任务）+ 向量删除"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.rag.ingest import IngestTask, run_ingest
from app.rag.vectorstore import get_vectorstore

router = APIRouter()


class IngestRequest(BaseModel):
    doc_id: int
    product_id: int | None = None
    doc_type: str
    doc_version: int
    file_url: str
    file_format: str


@router.post("/kb/ingest", status_code=202)
async def ingest(req: IngestRequest, background: BackgroundTasks):
    """提交摄取任务（后台执行，完成后回调后端回写状态）"""
    task = IngestTask(**req.model_dump())
    background.add_task(run_ingest, task)
    return {"task_id": f"ing_{req.doc_id}", "status": "ACCEPTED"}


@router.delete("/kb/docs/{doc_id}")
async def delete_doc(doc_id: int, version: int = 0):
    """删除文档向量；version>0 时保留该版本（重建索引用）"""
    deleted = await get_vectorstore().delete_by_doc(doc_id, exclude_version=version if version else None)
    return {"deleted": deleted}
