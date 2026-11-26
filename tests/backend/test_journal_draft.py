"""
行旅识景 TripScape / 手账草稿测试
创建日期: 2026-11-26

覆盖本轮修复:
    1. 存草稿不发布：status=draft、不公开、不生成足迹
    2. 连续保存草稿复用同一条记录（不再重复创建）
    3. 发布草稿后转为 approved 并生成足迹

依赖:
    依赖库: pytest, Django
"""

import pytest


@pytest.mark.django_db
def test_save_draft_does_not_publish(api_client, user_token, landmark):
    """存草稿：不公开、不进地标列表、不产生足迹。"""
    from apps.journals.models import Footprint

    response = api_client.json_post(
        "/api/journals/",
        {
            "landmark_id": landmark.id,
            "title": "草稿标题",
            "is_draft": True,
            "is_public": True,
        },
        token=user_token,
    )
    assert response.status_code == 200, response.content
    data = response.json()["data"]
    assert data["status"] == "draft"
    assert data["is_public"] is False
    assert Footprint.objects.filter(user__username="tester").count() == 0

    public = api_client.json_get(f"/api/journals/landmark/{landmark.id}")
    assert all(item["id"] != data["id"] for item in public.json()["data"])


@pytest.mark.django_db
def test_repeat_draft_save_reuses_record(api_client, user_token, landmark):
    """再次保存草稿走 PUT，不产生第二条记录。"""
    created = api_client.json_post(
        "/api/journals/",
        {"landmark_id": landmark.id, "title": "草稿一", "is_draft": True},
        token=user_token,
    )
    draft_id = created.json()["data"]["id"]

    updated = api_client.json_put(
        f"/api/journals/{draft_id}",
        {"title": "草稿二", "is_draft": True},
        token=user_token,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "草稿二"
    assert updated.json()["data"]["status"] == "draft"

    mine = api_client.json_get("/api/journals/mine", token=user_token)
    ids = [item["id"] for item in mine.json()["data"]]
    assert ids.count(draft_id) == 1
    assert len(ids) == 1


@pytest.mark.django_db
def test_publish_draft_creates_footprint(api_client, user_token, landmark):
    """发布草稿：转 approved、公开、足迹 +1。"""
    from apps.journals.models import Footprint

    created = api_client.json_post(
        "/api/journals/",
        {"landmark_id": landmark.id, "title": "待发布", "is_draft": True},
        token=user_token,
    )
    draft_id = created.json()["data"]["id"]

    published = api_client.json_put(
        f"/api/journals/{draft_id}",
        {"is_public": True, "is_draft": False},
        token=user_token,
    )
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "approved"
    assert published.json()["data"]["is_public"] is True
    assert Footprint.objects.filter(user__username="tester").count() == 1

    public = api_client.json_get(f"/api/journals/landmark/{landmark.id}")
    assert any(item["id"] == draft_id for item in public.json()["data"])
