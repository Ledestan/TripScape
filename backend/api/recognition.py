"""行旅识景 TripScape
创建日期：2025-09-01

识别 API（异步 Celery 任务 + 同步两种模式）。

POST /api/recognition/recognize   同步识别（兼容旧前端行为）
POST /api/recognition/submit      提交异步识别任务，返回 task_id
GET  /api/recognition/task/{id}   查询异步任务结果（前端轮询，
                                  等待期间发送按钮禁用，消息栏显示"识别中"）
"""


import logging

from apps.core.auth import login_required
from django.conf import settings
from ninja import Router
from ninja.errors import HttpError
from ninja.files import UploadedFile
from services import recognition_service as recognizer

router = Router()

logger = logging.getLogger("tripscape.recognition")

ALLOWED_EXTS = (".png", ".jpg", ".jpeg")
ALLOWED_MIME = ("image/png", "image/jpeg")


def _validate(file) -> bytes:
    """上传类型与大小校验（安全底线）。"""
    if file is None or not getattr(file, "name", ""):
        raise HttpError(400, "请上传图片文件")
    name = file.name.lower()
    if not name.endswith(ALLOWED_EXTS):
        raise HttpError(400, "仅支持 PNG、JPG 格式图片")
    data = file.read()
    if len(data) > settings.UPLOAD_MAX_SIZE:
        raise HttpError(
            400, f"图片大小不能超过 {settings.UPLOAD_MAX_SIZE // 1048576}MB"
        )
    if not data:
        raise HttpError(400, "文件为空")
    return data


@router.post("/recognize", summary="上传图片识别（同步）", auth=None)
def recognize_sync(request, image: UploadedFile = None):
    """同步图片识别（返回 top-3 与低置信度候选）。"""
    data = _validate(image)
    user = request.auth if getattr(request, "auth", None) else None
    result = recognizer.recognize_image(data, user=user)
    if not result.get("success"):
        return result
    return result


@router.post("/submit", summary="提交异步识别任务")
@login_required
def submit(request, image: UploadedFile = None):
    """提交异步识别任务（Celery）。"""
    data = _validate(image)
    # 暂存文件供 worker 读取
    import os
    import uuid

    from tasks.recognition_tasks import recognize_image_task

    stash_dir = settings.RUNTIME_TMP_DIR / "recognition"
    stash_dir.mkdir(parents=True, exist_ok=True)
    stash_path = stash_dir / f"{uuid.uuid4().hex}.jpg"
    with open(stash_path, "wb") as f:
        f.write(data)

    user = getattr(request, "auth", None)
    task = recognize_image_task.delay(
        str(stash_path), user_id=user.id if user else None
    )
    return {"success": True, "task_id": task.id, "status": "pending"}


@router.get("/task/{task_id}", summary="查询异步识别结果")
@login_required
def task_result(request, task_id: str):
    """查询异步任务结果。"""
    from tasks.recognition_tasks import get_result

    payload = get_result(task_id)
    if payload is None:
        return {"status": "pending"}
    payload["status"] = "done"
    return payload
