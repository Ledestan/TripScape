"""
行旅识景 TripScape / 文章点赞与徽章图标测试
创建日期: 2026-11-26

覆盖本轮新增能力:
    1. 文章（地标）可以被点赞，且状态接口能查回来
    2. 非法目标类型被拒绝
    3. 徽章图标不再是 emoji，而是可渲染的图标名

依赖:
    依赖库: pytest, Django
"""

import re

import pytest

ICON_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


@pytest.mark.django_db
def test_article_like_toggle(api_client, user_token, landmark):
    """文章点赞：toggle 两次回到未点赞。"""
    headers = {"HTTP_AUTHORIZATION": f"Bearer {user_token}"}

    on = api_client.json_post(
        "/api/likes/", {"target_type": "article", "target_id": landmark.id}, token=user_token
    )
    assert on.status_code == 200, on.content
    assert on.json()["liked"] is True
    assert on.json()["count"] == 1

    status = api_client.json_get(
        f"/api/likes/status?target_type=article&ids={landmark.id}", token=user_token
    )
    assert landmark.id in status.json()["liked_ids"]

    off = api_client.json_post(
        "/api/likes/", {"target_type": "article", "target_id": landmark.id}, token=user_token
    )
    assert off.json()["liked"] is False
    assert off.json()["count"] == 0


@pytest.mark.django_db
def test_article_like_rejects_unknown_target(api_client, user_token):
    """未知目标类型 400。"""
    response = api_client.json_post(
        "/api/likes/", {"target_type": "video", "target_id": 1}, token=user_token
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_badge_icons_are_names_not_emoji(api_client, user_token, badges):
    """徽章图标应是 lucide 名称（如 footprints），不是 emoji。"""
    response = api_client.json_get("/api/badges/mine", token=user_token)
    assert response.status_code == 200
    items = response.json()["data"]
    assert items, "至少要有徽章定义"
    for item in items:
        assert ICON_NAME.match(item["icon"]), f"图标不是名称：{item['icon']}"
