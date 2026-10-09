"""行旅识景 TripScape / 识别服务
创建日期：2025-10-08

识别入口：调度检索式引擎（DINOv2 + FAISS），完成:
    1. 检索引擎识别（top-3 候选 + 置信度）
    2. 结果组装（百科信息、低置信度候选、识别记录落库、热度累计）

引擎本体在 services/retrieval_engine.py（模型加载与索引装载）；
索引由 scripts/register_landmarks.py 构建。

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库: 同 retrieval_engine（torch / faiss-cpu）

用法:
    from services.recognition_service import recognize_image
    result = recognize_image(image_bytes, user=request.auth)

注意:
    1. 索引不存在时返回失败与重建指引，不做旧引擎回退（旧 VLAD 管线已删除）。
    2. 识别成功自动累计地标热度并写入 ts_recognition（看板统计用）。
"""

import logging
import time

from apps.landmarks.models import Landmark
from django.db.models import F
from django.conf import settings

logger = logging.getLogger(__name__)


def recognize_image(image_bytes: bytes, user=None) -> dict:
    """
    识别图片，返回地标 + 百科信息。

    返回：
        success/target_id/name/confidence/low_confidence/candidates
        加 image_url / intro / landmark_id / elapsed_ms / engine
    """
    started = time.time()

    from services.retrieval_engine import get_engine

    engine = get_engine()
    if engine is None:
        return {
            "success": False,
            "message": "识别索引不可用，请运行 python scripts/register_landmarks.py 构建",
        }

    try:
        results = engine.predict(image_bytes, top_k=3)
        if not results:
            return {"success": False, "message": "未能识别出地标"}

        # (target_id, 置信度) -> Landmark 实例
        lms = []
        for tid, conf in results:
            try:
                lms.append((Landmark.objects.get(target_id__iexact=tid), float(conf)))
            except Landmark.DoesNotExist:
                continue
        if not lms:
            return {"success": False, "message": "未能识别出地标"}

        return _build_result(lms, user, started, engine="retrieval")
    except Exception as exc:
        logger.exception("识别出错")
        return {"success": False, "message": f"识别出错: {exc}"}


def _build_result(results, user, started, engine):
    """
    统一构造识别结果：候选、低置信度标记、落库与热度。

    参数：
        results : list of (Landmark, float置信度)，按置信度降序
        engine : str，引擎名（日志与耗时口径）

    返回：
        dict，字段与前端约定一致
    """
    landmark, confidence = results[0]
    elapsed_ms = int((time.time() - started) * 1000)

    # 候选地标（低置信度时前端展示候选 + 搜索入口）
    candidates = []
    low_confidence = float(confidence) < settings.RECOG_CONFIDENCE_THRESHOLD
    if low_confidence:
        for cand_lm, cand_conf in results[1:]:
            candidates.append(
                {
                    "landmark_id": cand_lm.id,
                    "target_id": cand_lm.target_id,
                    "name": cand_lm.name,
                    "confidence": float(cand_conf),
                    "image_url": cand_lm.image_url,
                }
            )

    # 记录识别（运营看板用）；识别成功也顺带热度 +1
    try:
        from apps.landmarks.models import RecognitionRecord

        RecognitionRecord.objects.create(
            user=(user if (user and getattr(user, "is_authenticated", False)) else None),
            landmark=landmark,
            confidence=float(confidence),
            elapsed_ms=elapsed_ms,
        )
        Landmark.objects.filter(id=landmark.id).update(view_count=F("view_count") + 1)
    except Exception as exc:
        logger.warning("识别记录落库失败：%s", exc)

    return {
        "success": True,
        "engine": engine,
        "target_id": landmark.target_id,
        "name": landmark.name,
        "confidence": float(confidence),
        "confidence_percent": f"{confidence * 100:.1f}%",
        "image_url": landmark.image_url,
        "intro": landmark.intro,
        "landmark_id": landmark.id,
        "elapsed_ms": elapsed_ms,
        "low_confidence": low_confidence,
        "candidates": candidates,
    }
