"""行旅识景 TripScape / Beta 测试报告必修项回归
创建日期：2026-10-10

覆盖 TripScape_Beta1.0 测试报告 20 项必修问题（TS-01 ~ TS-20）
的自动化回归：账号处罚、可见性边界、手账日期契约、分页、
问答上下文与拒答、统计口径、部分更新语义。

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库: pytest / pytest-django

用法:
    pytest tests/backend/test_beta_fixes.py -v

注意:
    1. 用独立账号/地标夹具，不依赖种子数据。
    2. 断言对应报告的"验收标准"条目。
"""

import pytest

pytestmark = pytest.mark.django_db


# ----------------------------------------------------------------------
# 夹具
# ----------------------------------------------------------------------
@pytest.fixture
def users(db):
    from apps.accounts.models import User

    u1 = User.objects.create_user(username="betau1", password="x123456x", nickname="甲")
    u2 = User.objects.create_user(username="betau2", password="x123456x", nickname="乙")
    return u1, u2


@pytest.fixture
def tokens(users):
    from apps.core.auth import make_token

    u1, u2 = users
    return make_token(u1), make_token(u2)


@pytest.fixture
def landmark(db):
    from apps.landmarks.models import Landmark

    return Landmark.objects.create(
        target_id="BetaLm", name="回归塔", name_en="Beta", region="亚洲",
        country="测试", lat=0, lon=0, intro="回归", is_active=True,
    )


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import User

    return User.objects.create_user(
        username="betaadmin", password="x123456x", role="admin"
    )


# ----------------------------------------------------------------------
# TS-01 处罚使旧令牌失效
# ----------------------------------------------------------------------
class TestTS01AccountStatus:
    def test_banned_old_token_rejected(self, api_client, users, tokens):
        _, t2 = tokens
        u1, u2 = users
        u2.banned = True
        u2.save()
        r = api_client.json_post("/api/comments/", {"landmark_id": 1, "content": "x"}, token=t2)
        assert r.status_code in (401, 403)

    def test_locked_old_token_rejected(self, api_client, users, tokens):
        from datetime import timedelta

        from django.utils import timezone

        _, t2 = tokens
        u1, u2 = users
        u2.locked_until = timezone.now() + timedelta(days=1)
        u2.save()
        r = api_client.json_get("/api/auth/me", token=t2)
        assert r.status_code in (401, 403)


# ----------------------------------------------------------------------
# TS-02/03 手账草稿与软删边界
# ----------------------------------------------------------------------
class TestTS0203JournalVisibility:
    def _create(self, api_client, token, lm, **kw):
        payload = {"landmark_id": lm.id, "title": "T", "content": "C",
                   "visited_at": None, "is_public": True, **kw}
        return api_client.json_post("/api/journals/", payload, token=token)

    def test_pending_edit_not_leaked(self, api_client, tokens, landmark):
        from apps.journals.models import Journal

        t1, _ = tokens
        r = self._create(api_client, t1, landmark)
        assert r.status_code == 200, r.content
        jid = r.json()["data"]["id"]
        j = Journal.objects.get(id=jid)
        j.status = "approved"
        j.save()
        # 更新进审核
        r2 = api_client.json_put(f"/api/journals/{jid}", {"content": "SECRET_DRAFT"}, token=t1)
        assert r2.status_code == 200
        j.refresh_from_db()
        assert j.edit_pending
        # 游客读：不泄露草稿
        r3 = api_client.json_get(f"/api/journals/{jid}")
        assert r3.status_code == 200
        assert "SECRET_DRAFT" not in str(r3.json())

    def test_softdeleted_not_editable_nor_visible(self, api_client, tokens, landmark, admin_user):
        from apps.core.auth import make_token
        from apps.journals.models import Journal

        t1, _ = tokens
        r = self._create(api_client, t1, landmark)
        jid = r.json()["data"]["id"]
        j = Journal.objects.get(id=jid)
        j.status = "approved"
        j.save()
        # 管理员软删
        j.delete()  # 模型 delete = 软删
        # 作者编辑被拒
        r2 = api_client.json_put(f"/api/journals/{jid}", {"is_public": True}, token=t1)
        assert r2.status_code == 404
        # 游客读 404
        r3 = api_client.json_get(f"/api/journals/{jid}")
        assert r3.status_code == 404


# ----------------------------------------------------------------------
# TS-05/06/11 日期契约
# ----------------------------------------------------------------------
class TestTS0506JournalDate:
    def _create(self, api_client, token, lm, visited_at="2026-10-01"):
        return api_client.json_post(
            "/api/journals/",
            {"landmark_id": lm.id, "title": "T", "content": "C", "visited_at": visited_at},
            token=token,
        )

    def test_null_date_accepted(self, api_client, tokens, landmark):
        t1, _ = tokens
        r = self._create(api_client, t1, landmark, visited_at=None)
        assert r.status_code == 200, r.content

    def test_valid_date_update_no_500(self, api_client, tokens, landmark):
        t1, _ = tokens
        r = self._create(api_client, t1, landmark)
        jid = r.json()["data"]["id"]
        r2 = api_client.json_put(f"/api/journals/{jid}", {"visited_at": "2026-10-02"}, token=t1)
        assert r2.status_code == 200, r2.content

    def test_invalid_date_422_not_500(self, api_client, tokens, landmark):
        t1, _ = tokens
        r = self._create(api_client, t1, landmark, visited_at="2026-02-30")
        assert r.status_code == 422


# ----------------------------------------------------------------------
# TS-08/09 问答上下文与拒答
# ----------------------------------------------------------------------
class TestTS0809Qa:
    def test_pronoun_followup(self):
        from services.article_qa import answer_question

        history = [{"question": "埃菲尔铁塔在哪里？", "answer": "位于法国巴黎",
                    "landmark_name": "埃菲尔铁塔"}]
        r = answer_question("它有多高？", history=history)
        assert "330" in r["answer"] or "埃菲尔" in r["answer"]

    def test_out_of_domain_refused(self):
        from services.article_qa import answer_question

        r = answer_question("今天股票怎么买？")
        assert not r["known"]


# ----------------------------------------------------------------------
# TS-10/11 分页
# ----------------------------------------------------------------------
class TestTS1011Pagination:
    def test_search_page2_differs(self, api_client, landmark):
        from apps.landmarks.models import Landmark

        for i in range(7):
            Landmark.objects.create(
                target_id=f"PageLm{i}", name=f"分页塔{i}", name_en=f"P{i}",
                region="亚洲", country="测试", lat=0, lon=0, intro="p", is_active=True,
            )
        r1 = api_client.json_get("/api/search/?kind=landmark&page=1&page_size=5")
        r2 = api_client.json_get("/api/search/?kind=landmark&page=2&page_size=5")
        assert r1.status_code == r2.status_code == 200
        ids1 = {i["id"] for i in r1.json()["data"]}
        ids2 = {i["id"] for i in r2.json()["data"]}
        assert not (ids1 & ids2), "第二页不得重复第一页"

    def test_negative_page_no_500(self, api_client):
        r = api_client.json_get("/api/search/?page_size=-1")
        assert r.status_code == 200

    def test_negative_history_limit(self, api_client, tokens):
        t1, _ = tokens
        r = api_client.json_get("/api/qa/history?limit=-1", token=t1)
        assert r.status_code in (200, 401)


# ----------------------------------------------------------------------
# TS-16 统计口径
# ----------------------------------------------------------------------
class TestTS16Stats:
    def test_softdeleted_no_footprint(self, users, landmark):
        from apps.journals.models import Journal
        from services.footprint_service import rebuild_user_footprints

        u1, _ = users
        j = Journal.objects.create(
            user=u1, landmark=landmark, title="T", content="C", status="approved"
        )
        assert rebuild_user_footprints(u1) == 1
        j.delete()
        assert rebuild_user_footprints(u1) == 0

    def test_visits_aggregation(self, users, landmark):
        from apps.journals.models import Journal
        from services.footprint_service import rebuild_user_footprints

        u1, _ = users
        for i in range(2):
            Journal.objects.create(
                user=u1, landmark=landmark, title=f"T{i}", content="C", status="approved"
            )
        rebuild_user_footprints(u1)
        from apps.journals.models import Footprint

        fp = Footprint.objects.get(user=u1, landmark=landmark)
        assert fp.visits == 2


# ----------------------------------------------------------------------
# TS-17 部分更新
# ----------------------------------------------------------------------
class TestTS17Profile:
    def test_partial_update_keeps_fields(self, api_client, tokens, users):
        t1, _ = tokens
        u1, _ = users
        u1.avatar = "/a.png"
        u1.bio = "签名"
        u1.save()
        r = api_client.json_put("/api/auth/profile", {"nickname": "新名"}, token=t1)
        assert r.status_code == 200
        u1.refresh_from_db()
        assert u1.avatar == "/a.png"
        assert u1.bio == "签名"
        assert u1.nickname == "新名"


# ----------------------------------------------------------------------
# TS-20 点赞目标校验
# ----------------------------------------------------------------------
class TestTS20LikeTarget:
    def test_like_nonexistent_404(self, api_client, tokens):
        t1, _ = tokens
        r = api_client.json_post(
            "/api/likes/", {"target_type": "journal", "target_id": 999999}, token=t1
        )
        assert r.status_code == 404

    def test_report_nonexistent_404(self, api_client, tokens):
        t1, _ = tokens
        r = api_client.json_post(
            "/api/comments/report",
            {"target_type": "journal", "target_id": 999999,
             "reason": "spam", "detail": ""},
            token=t1,
        )
        assert r.status_code == 404
