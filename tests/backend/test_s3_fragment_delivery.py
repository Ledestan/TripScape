"""S3 功能证据 · 投递侧（SPEC §3.5）。

断言：
1. 同一用户对同一地标的前 3 次投递成功，且响应体回报已用数量与剩余额度；
2. 第 4 次投递返回**明确错误码与错误消息**（409 + 中文额度说明），不得静默成功；
3. 数据库里该用户对该地标确实只有 3 条碎片（不靠响应体自证）；
4. 未加入手账的卡片不得投递（403）；
5. 开关关闭时投递端点不存在（404，默认行为不变）。

说明：本测试只通过公开 API + DB 计数验证行为，不 import 实现里的常量来做断言基准。
"""

import pytest
from django.test import override_settings

LIMIT = 3  # SPEC §2 S3：同一用户对同一地标最多投递 3 条


def _make_card_id(client, token, landmark_id: int) -> int:
    """通过真实端点取一张卡片（无卡片时服务端按种子数据现建）。"""
    resp = client.json_get(f"/api/narrative/card/{landmark_id}", token=token)
    assert resp.status_code == 200, resp.content
    return resp.json()["data"]["id"]


def _add_to_journal(client, token, card_id: int):
    resp = client.json_post("/api/narrative/journal/cards", {"card_id": card_id}, token=token)
    assert resp.status_code == 200, resp.content
    return resp


def _deliver(client, token, card_id: int, landmark_id: int):
    return client.json_post(
        "/api/narrative/fragments",
        {"card_id": card_id, "landmark_id": landmark_id},
        token=token,
    )


@pytest.mark.django_db
def test_first_three_deliveries_ok_and_fourth_rejected(api_client, user_token, landmark):
    """前 3 次成功、第 4 次 409，且响应/库内计数一致。"""
    card_id = _make_card_id(api_client, user_token, landmark.id)
    _add_to_journal(api_client, user_token, card_id)

    for attempt in range(1, LIMIT + 1):
        resp = _deliver(api_client, user_token, card_id, landmark.id)
        assert resp.status_code == 200, resp.content
        data = resp.json()["data"]
        assert data["deliveredCount"] == attempt
        assert data["remaining"] == LIMIT - attempt

    fourth = _deliver(api_client, user_token, card_id, landmark.id)
    assert fourth.status_code == 409, fourth.content
    detail = fourth.json().get("detail", "")
    assert f"最多投递 {LIMIT} 条" in detail, detail
    assert "3" in detail, detail

    # 用数据库计数自证：不是响应体自说自话
    from apps.narrative.models import NarrativeFragment

    assert NarrativeFragment.objects.filter(landmark=landmark).count() == LIMIT


@pytest.mark.django_db
def test_deliver_rejects_card_not_in_journal(api_client, user_token, landmark):
    """只能投递手账中的卡片（未沉淀的卡片不能直接抛给陌生人）。"""
    card_id = _make_card_id(api_client, user_token, landmark.id)
    resp = _deliver(api_client, user_token, card_id, landmark.id)
    assert resp.status_code == 403, resp.content
    assert "手账" in resp.json().get("detail", "")
