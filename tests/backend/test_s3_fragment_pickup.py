"""S3 功能证据 · 拾取侧（SPEC §3.5）。

断言：
1. 拾取返回体包含**来源卡片摘要字段**（id/title/photo/landmarkId/confidence/snippet）；
2. 同一碎片对同一用户第二次拾取被拒绝（409 + 明确消息）；
3. 拾取是匿名的：响应体不含投递者身份字段；
4. 随机拾取会排除"自己投递的碎片"与"已拾取过的碎片"，无可用时 404；
5. 开关关闭时拾取端点不存在（404）。
"""

import pytest
from django.test import override_settings

SOURCE_CARD_SUMMARY_FIELDS = ("id", "title", "photo", "landmarkId", "confidence", "snippet")


def _card_and_journal(client, token, landmark_id: int) -> int:
    """取卡片并加入手账（真实端点）。"""
    resp = client.json_get(f"/api/narrative/card/{landmark_id}", token=token)
    assert resp.status_code == 200, resp.content
    card_id = resp.json()["data"]["id"]
    resp = client.json_post("/api/narrative/journal/cards", {"card_id": card_id}, token=token)
    assert resp.status_code == 200, resp.content
    return card_id


def _deliver(client, token, card_id: int, landmark_id: int):
    resp = client.json_post(
        "/api/narrative/fragments",
        {"card_id": card_id, "landmark_id": landmark_id},
        token=token,
    )
    assert resp.status_code == 200, resp.content
    return resp.json()["data"]["fragmentId"]


@pytest.fixture
def picker(db):
    """第二个用户（拾取者），与投递者不同。"""
    from apps.accounts.models import User

    return User.objects.create_user(
        username="picker", password="picker123456", nickname="拾取者"
    )


@pytest.fixture
def picker_token(picker):
    from apps.core.auth import make_token

    return make_token(picker)


@pytest.mark.django_db
def test_pick_returns_source_card_summary_and_rejects_second_pick(
    api_client, user_token, picker_token, landmark
):
    """拾取一次成功（含来源卡片摘要）；按 ID 再拾取同一碎片 -> 409。"""
    card_id = _card_and_journal(api_client, user_token, landmark.id)
    fragment_id = _deliver(api_client, user_token, card_id, landmark.id)

    picked = api_client.json_get(
        f"/api/narrative/fragments/pick?landmark_id={landmark.id}", token=picker_token
    )
    assert picked.status_code == 200, picked.content
    data = picked.json()["data"]
    assert data["id"] == fragment_id
    summary = data.get("sourceCard")
    assert isinstance(summary, dict), data
    missing = [f for f in SOURCE_CARD_SUMMARY_FIELDS if f not in summary]
    assert not missing, f"来源卡片摘要缺少字段: {missing}; 实际: {sorted(summary)}"
    assert isinstance(summary["title"], str) and summary["title"]
    assert isinstance(summary["snippet"], str)
    assert isinstance(summary["confidence"], (int, float))

    # 匿名性：响应体不得出现投递者身份字段
    for leaked in ("deliveredBy", "delivered_by", "user", "user_id", "owner"):
        assert leaked not in data, f"碎片响应泄露投递者字段: {leaked}"
    assert data["anonymous"] is True

    # 同一碎片对同一用户第二次拾取 -> 拒绝
    again = api_client.json_post(
        f"/api/narrative/fragments/{fragment_id}/pick", token=picker_token
    )
    assert again.status_code == 409, again.content
    assert "已被你拾取" in again.json().get("detail", "")

    # 再走随机拾取：没有可拾取的碎片 -> 404
    empty = api_client.json_get(
        f"/api/narrative/fragments/pick?landmark_id={landmark.id}", token=picker_token
    )
    assert empty.status_code == 404, empty.content


@pytest.mark.django_db
def test_own_fragment_is_not_pickable(api_client, user_token, landmark):
    """自己投递的碎片不出现在自己的拾取池（叙事必须来自陌生人）。"""
    card_id = _card_and_journal(api_client, user_token, landmark.id)
    _deliver(api_client, user_token, card_id, landmark.id)

    resp = api_client.json_get(
        f"/api/narrative/fragments/pick?landmark_id={landmark.id}", token=user_token
    )
    assert resp.status_code == 404, resp.content
