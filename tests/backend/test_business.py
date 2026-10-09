"""业务流程测试：评论（敏感词）/ 手账（足迹）/ 徽章 / 分享。"""


class TestComments:
    def test_create_comment(self, api_client, user, user_token, landmark):
        r = api_client.json_post(
            "/api/comments/",
            {"landmark_id": landmark.id, "content": "很棒的地方！"},
            token=user_token,
        )
        assert r.status_code == 200
        assert r.json()["data"]["content"] == "很棒的地方！"

    def test_sensitive_word_blocked(self, api_client, user_token, landmark):
        r = api_client.json_post(
            "/api/comments/",
            {"landmark_id": landmark.id, "content": "加微信刷单赚钱"},
            token=user_token,
        )
        assert r.status_code == 400
        assert "敏感词" in r.json()["detail"]

    def test_public_list(self, api_client, user, user_token, landmark):
        api_client.json_post(
            "/api/comments/",
            {"landmark_id": landmark.id, "content": "公开评论"},
            token=user_token,
        )
        r = api_client.json_get(f"/api/comments/landmark/{landmark.id}")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


class TestJournalAndFootprint:
    def test_journal_creates_footprint(
        self, api_client, user, user_token, landmark, badges
    ):
        r = api_client.json_post(
            "/api/journals/",
            {
                "landmark_id": landmark.id,
                "title": "游记",
                "content": "内容",
                "is_public": True,
            },
            token=user_token,
        )
        assert r.status_code == 200
        jid = r.json()["data"]["id"]

        # 足迹自动生成（取消手动打卡）
        r = api_client.json_get("/api/footprints/mine", token=user_token)
        assert r.status_code == 200
        assert r.json()["data"][0]["name"] == "测试塔"

        # 徽章自动发放
        r = api_client.json_get("/api/badges/mine", token=user_token)
        owned = [b["name"] for b in r.json()["data"] if b["owned"]]
        assert "初次远行" in owned and "第一篇手账" in owned

        # 分享链接（免登录可看）
        r = api_client.json_post(f"/api/journals/{jid}/share", token=user_token)
        assert r.status_code == 200
        share_token = r.json()["token"]
        r = api_client.json_get(f"/api/shares/{share_token}")
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "游记"


class TestLandmarks:
    def test_spots(self, api_client, landmark):
        r = api_client.json_get("/api/landmarks/spots")
        assert r.status_code == 200
        assert any(s["name"] == "测试塔" for s in r.json()["data"])

    def test_detail_increments_view(self, api_client, landmark):
        r = api_client.json_get(f"/api/landmarks/{landmark.id}")
        assert r.status_code == 200
        assert r.json()["data"]["intro"] == "测试用百科介绍"
        landmark.refresh_from_db()
        assert landmark.view_count == 1

    def test_search_orm_fallback(self, api_client, landmark):
        from urllib.parse import quote

        r = api_client.json_get(f"/api/search/?q={quote('测试塔')}")
        assert r.status_code == 200
        assert r.json()["source"] in ("orm", "meilisearch")
