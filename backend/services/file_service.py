"""行旅识景 TripScape
创建日期：2025-09-01

文件服务：MinIO 优先，本地 runtime/uploads 兜底。

所有上传内容统一进 runtime/uploads（开发态本地磁盘，
MinIO 可用时写对象存储并把 public URL 返回）。
"""

import logging
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger("tripscape.uploads")

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif"}

_client = None
_client_checked = False


def get_minio():
    """获取 MinIO 客户端（懒加载；不可用返回 None -> 本地磁盘兜底）。"""
    global _client, _client_checked
    if _client is None and not _client_checked:
        _client_checked = True
        try:
            from minio import Minio

            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            if not client.bucket_exists(settings.MINIO_BUCKET):
                client.make_bucket(settings.MINIO_BUCKET)
                logger.info("MinIO bucket %s 已创建", settings.MINIO_BUCKET)
            _client = client
        except Exception as exc:
            logger.warning("MinIO 不可用，使用本地存储：%s", exc)
            _client = None
    return _client


def validate(file: UploadedFile) -> str:
    """上传类型校验（安全底线）。异常直接抛 HttpError。"""
    from ninja.errors import HttpError

    if file is None or not getattr(file, "name", ""):
        raise HttpError(400, "请上传文件")
    name = file.name.lower()
    ext = Path(name).suffix
    if ext not in ALLOWED_EXTS:
        raise HttpError(400, "仅支持 PNG / JPG / WEBP / GIF 图片")
    if file.size and file.size > settings.UPLOAD_MAX_SIZE:
        raise HttpError(400, f"文件大小超过 {settings.UPLOAD_MAX_SIZE // 1048576}MB")
    # 读魔数兜底（伪造扩展名拦截）
    file.seek(0)
    header = file.read(16)
    file.seek(0)
    if not _valid_magic(header):
        raise HttpError(400, "文件内容不是有效图片")
    return ext


def _valid_magic(header: bytes) -> bool:
    if header.startswith(b"\x89PNG"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return True
    return False


def save_upload(file: UploadedFile, namespace: str = "misc", owner=None) -> str:
    """保存上传文件，返回可访问 URL。

    - MinIO 可用：写入对象存储，返回 MINIO_PUBLIC_URL/bucket/key
    - 否则：写入 runtime/uploads/<namespace>/，返回 /media/<namespace>/xxx
    """
    ext = validate(file)
    safe_ns = re.sub(r"[^a-z0-9_-]", "", namespace.lower()) or "misc"
    key = f"{safe_ns}/{uuid.uuid4().hex}{ext}"

    client = get_minio()
    if client is not None:
        try:
            from io import BytesIO

            from minio.error import S3Error

            data = file.read()
            client.put_object(
                settings.MINIO_BUCKET,
                key,
                BytesIO(data),
                length=len(data),
                content_type=file.content_type or "application/octet-stream",
            )
            return (
                f"{settings.MINIO_PUBLIC_URL.rstrip('/')}/{settings.MINIO_BUCKET}/{key}"
            )
        except Exception as exc:
            logger.warning("MinIO 写入失败，回退本地：%s", exc)

    # 本地兜底
    dest = settings.RUNTIME_UPLOADS_DIR / safe_ns
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / Path(key).name
    with open(path, "wb") as out:
        for chunk in file.chunks():
            out.write(chunk)
    return f"{settings.MEDIA_URL}{safe_ns}/{path.name}"
