"""
行旅识景 TripScape / 上传接口测试
创建日期: 2026-11-26

校验画布照片依赖的图片上传接口，覆盖:
    1. 登录后才能上传
    2. 只接受图片，且做文件头校验
    3. 成功返回站内 /media/ 地址

依赖:
    依赖库: pytest, Django

用法:
    python -m pytest tests/backend/test_uploads.py -v

注意:
    只断言接口契约与落盘路径，不校验图片内容本身。
"""

import base64

import pytest

# 1×1 透明 PNG
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


def _png():
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile("trip.png", base64.b64decode(PNG_BASE64), content_type="image/png")


@pytest.mark.django_db
def test_upload_requires_login(api_client):
    """未登录不能上传。"""
    response = api_client.post("/api/uploads/image", {"image": _png()})
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_upload_rejects_non_image(api_client, user_token):
    """非图片（文件头不对）被拒绝。"""
    from django.core.files.uploadedfile import SimpleUploadedFile

    fake = SimpleUploadedFile("evil.png", b"not-an-image", content_type="image/png")
    headers = {"HTTP_AUTHORIZATION": f"Bearer {user_token}"}
    response = api_client.post("/api/uploads/image", {"image": fake}, **headers)
    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_returns_media_url(api_client, user_token):
    """成功上传返回 /media/ 地址。"""
    headers = {"HTTP_AUTHORIZATION": f"Bearer {user_token}"}
    response = api_client.post("/api/uploads/image", {"image": _png()}, **headers)
    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["success"] is True
    assert payload["url"].startswith("/media/journals/")
    assert payload["url"].endswith(".png")
