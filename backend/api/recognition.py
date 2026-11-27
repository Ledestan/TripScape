"""
行旅识景 TripScape / api/recognition

识别 API（异步 Celery 任务 + 同步两种模式）。

POST /api/recognition/recognize   同步识别（兼容旧前端行为）
POST /api/recognition/submit      提交异步识别任务，返回 task_id
GET  /api/recognition/task/{id}   查询异步任务结果（前端轮询，
                                  等待期间发送按钮禁用，消息栏显示"识别中"）
"""

import logging

from apps.core.auth import OptionalAuth, login_required
from apps.core.net import client_ip
from apps.core.ratelimit import heavy_limiter
from django.conf import settings
from ninja import Router
from ninja.errors import HttpError
from ninja.files import UploadedFile
from services import recognition_service as recognizer

router = Router()

logger = logging.getLogger("tripscape.recognition")

ALLOWED_EXTS = (".png", ".jpg", ".jpeg")
ALLOWED_MIME = ("image/png", "image/jpeg")

# 单 IP 每分钟识别次数（模型推理是重接口，匿名可调，必须限流）
RECOGNIZE_PER_MINUTE = 10


def _valid_magic(header: bytes) -> bool:
    """图片文件头校验（只认 PNG / JPEG）。"""
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    return False


def _validate(file) -> bytes:
    """上传类型与大小校验（安全底线：扩展名 + 文件头 + 大小）。"""
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
    # 扩展名可伪造：必须校验魔数，否则非图片字节会直接喂给图像库
    if not _valid_magic(data[:16]):
        raise HttpError(400, "文件内容不是有效图片")
    return data


@router.post("/recognize", summary="上传图片识别（同步）", auth=OptionalAuth())
def recognize_sync(request, image: UploadedFile = None, photo_url: str = ""):
    """同步图片识别（返回 top-3 与低置信度候选）。

    成功响应额外携带叙事卡片字段（SPEC §2 S2；2.0 默认行为）：
        id / landmarkId / photo / title / geo / timeFragments /
        ragSnippets / confidence / source
    开关关闭时响应与既有行为完全一致（新增键不出现）。
    """
    ip = client_ip(request)
    if not heavy_limiter.allow(
        f"recognize:{ip}", limit=RECOGNIZE_PER_MINUTE, window_seconds=60
    ):
        raise HttpError(429, "识别过于频繁，请稍后再试")
    data = _validate(image)
    user = request.auth if getattr(request.auth, "is_authenticated", False) else None
    result = recognizer.recognize_image(data, user=user)
    if not result.get("success"):
        return result
    # 2.0 本体：识别成功即附带叙事卡片（组装失败不影响识别结果）
    _attach_narrative_card(result, user=user, photo_url=photo_url)
    return result


def _attach_narrative_card(result: dict, *, user=None, photo_url: str = "") -> None:
    """把叙事卡片字段并入识别响应（原地更新，失败不影响识别结果）。"""
    from apps.landmarks.models import Landmark
    from services import narrative_service

    landmark = Landmark.objects.filter(id=result.get("landmark_id")).first()
    if landmark is None:
        return
    try:
        card = narrative_service.build_narrative_card(
            landmark,
            user=user,
            photo=photo_url,
            confidence=float(result.get("confidence") or 0.0),
            source=str(result.get("engine") or "retrieval"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("叙事卡片组装失败（不影响识别）：%s", exc)
        return
    result.update(card.as_card())


def _celery_available() -> bool:
    """Celery 任务链是否可用（打包分发包不带 worker，TS-18）。

    探测方式：导入 celery.loaders.default（PyInstaller 收集不全时
    正是它缺）；失败即视为异步能力不可用。
    """
    try:
        import celery.loaders.default  # noqa: F401
        from config.celery import app as celery_app

        return bool(celery_app.conf.broker_url)
    except Exception:
        return False


@router.post("/submit", summary="提交异步识别任务")
@login_required
def submit(request, image: UploadedFile = None):
    """提交异步识别任务（Celery；分发包无 worker 时明确 503，TS-18）。"""
    if not _celery_available():
        raise HttpError(503, "异步识别在当前环境不可用，请使用同步识别接口")
    ip = client_ip(request)
    if not heavy_limiter.allow(
        f"recognize-submit:{ip}", limit=RECOGNIZE_PER_MINUTE, window_seconds=60
    ):
        raise HttpError(429, "提交过于频繁，请稍后再试")
    data = _validate(image)
    # 暂存文件供 worker 读取（目录来自 settings，文件名用 uuid 防冲突）
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
    """查询异步任务结果（分发包无 Celery 时明确 503，TS-18）。"""
    if not _celery_available():
        raise HttpError(503, "异步识别在当前环境不可用")
    from tasks.recognition_tasks import get_result

    payload = get_result(task_id)
    if payload is None:
        return {"status": "pending"}
    # 任务归属校验：任务 ID 不是访问凭据，别人的任务结果不能看
    owner_id = payload.pop("_owner_id", None)
    if owner_id is not None and owner_id != request.auth.id:
        raise HttpError(403, "无权查看该识别任务")
    payload["status"] = "done"
    return payload
