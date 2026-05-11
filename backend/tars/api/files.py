"""TARS API - 文件上传路由"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Any, Dict

from ..files import FileStorage

router = APIRouter(prefix="/api/files", tags=["文件管理"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 全局实例，在 main.py 中初始化
_storage: FileStorage = None


def init_file_storage(storage: FileStorage):
    global _storage
    _storage = storage


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件"""
    if not _storage:
        raise HTTPException(status_code=503, detail="文件存储未初始化")

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大（>{MAX_FILE_SIZE // 1024 // 1024}MB），无法通过 HTTP 上传。如文件在本地项目目录中，请直接告诉我文件路径，我会使用读取工具直接解析。")

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    try:
        record = await _storage.save(file.filename, content)
        preview = _storage.generate_preview(record)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    return {
        "success": True,
        "file": {
            "file_id": record.file_id,
            "name": record.name,
            "type": record.type,
            "mime_type": record.mime_type,
            "size": record.size,
            "preview": preview,
        },
    }


@router.get("/{file_id}")
async def get_file_info(file_id: str):
    """获取文件信息"""
    if not _storage:
        raise HTTPException(status_code=503, detail="文件存储未初始化")

    record = _storage.get(file_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"文件 '{file_id}' 不存在")

    return {"success": True, "file": record.to_dict()}


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """删除文件"""
    if not _storage:
        raise HTTPException(status_code=503, detail="文件存储未初始化")

    if _storage.delete(file_id):
        return {"success": True, "message": "文件已删除"}
    raise HTTPException(status_code=404, detail=f"文件 '{file_id}' 不存在")
