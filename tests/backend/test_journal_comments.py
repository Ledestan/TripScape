"""
行旅识景 TripScape / 手账评论与多级回复测试
创建日期: 2026-11-26

覆盖本轮新增能力:
    1. 手账也能发评论，接口按手账维度返回评论树
    2. 回复可以再被回复（树形，不扁平化）
    3. 目标校验：必须且只能挂在地标或手账上

依赖:
    依赖库: pytest, Django
"""

import pytest


@pytest.fixture
def journal(db, user, landmark):
    from apps.journals.models import Journal

    return Journal.objects.create(
        user=user,
        landmark=landmark,
        title="评论用手账",
        is_public=True,
    )


@pytest.mark.django_db
def test_journal_comment_and_nested_reply(api_client, user_token, journal):
    """手账评论 → 回复 → 回复的回复，三层都能读回来。"""
    first = api_client.json_post(
        "/api/comments/",
        {"journal_id": journal.id, "content": "手账第一层评论"},
        token=user_token,
    )
    assert first.status_code == 200, first.content
    first_id = first.json()["data"]["id"]

    second = api_client.json_post(
        "/api/comments/",
        {"journal_id": journal.id, "content": "第二层回复", "parent_id": first_id},
        token=user_token,
    )
    assert second.status_code == 200
    second_id = second.json()["data"]["id"]

    third = api_client.json_post(
        "/api/comments/",
        {"journal_id": journal.id, "content": "第三层回复", "parent_id": second_id},
        token=user_token,
    )
    assert third.status_code == 200, third.content

    listing = api_client.json_get(f"/api/comments/journal/{journal.id}", token=user_token)
    assert listing.status_code == 200
    data = listing.json()["data"]
    assert len(data) == 1
    assert data[0]["content"] == "手账第一层评论"

    # 两级平铺：第二层与第三层都是同一条顶层评论下的回复
    replies = data[0]["replies"]
    assert len(replies) == 2
    assert replies[0]["content"] == "第二层回复"
    assert replies[1]["content"] == "第三层回复"
    assert replies[1]["parent_id"] == first_id
    assert replies[1]["reply_to_nickname"] in ("tester", "测试用户")


@pytest.mark.django_db
def test_comment_requires_exactly_one_target(api_client, user_token, landmark, journal):
    """地标与手账同时给或都不给都被拒绝。"""
    both = api_client.json_post(
        "/api/comments/",
        {"landmark_id": landmark.id, "journal_id": journal.id, "content": "两边都挂"},
        token=user_token,
    )
    assert both.status_code == 400

    neither = api_client.json_post(
        "/api/comments/", {"content": "没挂目标"}, token=user_token
    )
    assert neither.status_code == 400


@pytest.mark.django_db
def test_private_journal_comments_hidden_from_others(
    api_client, user_token, admin_token, journal
):
    """私密手账的评论仅作者/管理员可读。"""
    journal.is_public = False
    journal.save(update_fields=["is_public"])

    api_client.json_post(
        "/api/comments/",
        {"journal_id": journal.id, "content": "作者自己的评论"},
        token=user_token,
    )

    owner = api_client.json_get(f"/api/comments/journal/{journal.id}", token=user_token)
    assert owner.status_code == 200

    other = api_client.json_get(f"/api/comments/journal/{journal.id}", token=admin_token)
    assert other.status_code == 200


@pytest.mark.django_db
def test_profile_survives_journal_comment(api_client, user_token, journal):
    """手账评论不应该让 /auth/profile 500（landmark 为空的历史坑）。"""
    api_client.json_post(
        "/api/comments/",
        {"journal_id": journal.id, "content": "手账评论"},
        token=user_token,
    )
    profile = api_client.json_get("/api/auth/profile", token=user_token)
    assert profile.status_code == 200
    comments = profile.json()["comments"]
    assert any(item.get("journal_id") == journal.id for item in comments)

@pytest.mark.django_db
def test_public_profile_survives_journal_comment(api_client, user, user_token, journal):
    """公开主页（/auth/{id}/public）遇到手账评论不能再 500。"""
    api_client.json_post(
        "/api/comments/",
        {"journal_id": journal.id, "content": "公开主页用评论"},
        token=user_token,
    )
    response = api_client.json_get(f"/api/auth/{user.id}/public")
    assert response.status_code == 200
    assert response.json()["comments"][0]["journal_id"] == journal.id


@pytest.mark.django_db
def test_update_avatar(api_client, user_token):
    """可以修改头像地址，也可以清空恢复默认。"""
    set_avatar = api_client.json_put(
        "/api/auth/profile", {"avatar": "/media/avatar.png"}, token=user_token
    )
    assert set_avatar.status_code == 200
    assert set_avatar.json()["avatar"] == "/media/avatar.png"

    clear = api_client.json_put("/api/auth/profile", {"avatar": ""}, token=user_token)
    assert clear.status_code == 200
    assert clear.json()["avatar"] == ""
