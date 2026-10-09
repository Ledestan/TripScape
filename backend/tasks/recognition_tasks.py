"""行旅识景 TripScape
创建日期：2025-09-01

landmarks 异步任务：识别 + 知识库重建向量索引。
"""

import logging
import os
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger("tripscape.tasks")


@shared_task(name="tasks.recognition_tasks.recognize_image_task")
def recognize_image_task(image_path: str, user_id=None):
    """异步识别图片（image_path 为 runtime/tmp 下的暂存文件）。"""
    from apps.landmarks.models import Landmark, RecognitionRecord
    from django.contrib.auth import get_user_model
    from services import recognition_service as recognizer

    User = get_user_model()
    user = User.objects.filter(id=user_id).first() if user_id else None

    path = Path(image_path)
    if not path.exists():
        return {"success": False, "message": "暂存图片已过期，请重新上传"}

    data = path.read_bytes()
    result = recognizer.recognize_image(data, user=user)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

    if result.get("success") and user:
        # 异步识别成功后为用户生成一条"待确认手账"提示数据（不自动创建手账）
        pass
    return result


@shared_task(name="tasks.recognition_tasks.refresh_all_footprints")
def refresh_all_footprints():
    """全量重建所有用户足迹（手账自动生成）。"""
    from django.contrib.auth import get_user_model
    from services import footprint_service

    User = get_user_model()
    total = 0
    for user in User.objects.filter(is_active=True).iterator():
        total += footprint_service.rebuild_user_footprints(user)
    return {"footprints": total}


def get_result(task_id: str):
    """查询 Celery 异步任务结果（无结果后端时返回 None）。"""
    from celery.result import AsyncResult

    res = AsyncResult(task_id)
    if not res.ready():
        return None
    try:
        return (
            res.result
            if res.successful()
            else {"success": False, "message": str(res.result)}
        )
    except Exception:
        return None
