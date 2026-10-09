"""pytest 共享 fixtures。"""

import os
import sys
from pathlib import Path

# 根除 __pycache__（对 pytest 进程及其导入的全部子模块生效）
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


@pytest.fixture
def api_client():
    """Django test client（JSON 请求便捷封装）。"""
    from django.test import Client

    class JsonClient(Client):
        def json_post(self, path, data=None, token=None, **kw):
            import json

            headers = kw.pop("headers", {})
            if token:
                headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
            return self.post(
                path,
                data=json.dumps(data or {}),
                content_type="application/json",
                **headers,
                **kw,
            )

        def json_get(self, path, token=None, **kw):
            headers = kw.pop("headers", {})
            if token:
                headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
            return self.get(path, **headers, **kw)

    return JsonClient()


@pytest.fixture
def user(db):
    from apps.accounts.models import User

    return User.objects.create_user(
        username="tester", password="pass123456", nickname="测试用户"
    )


@pytest.fixture
def user_token(user):
    from apps.core.auth import make_token

    return make_token(user)


@pytest.fixture
def admin(db):
    from apps.accounts.models import User

    return User.objects.create_user(
        username="root", password="pass123456", role="admin", is_staff=True
    )


@pytest.fixture
def admin_token(admin):
    from apps.core.auth import make_token

    return make_token(admin)


@pytest.fixture
def landmark(db):
    from apps.landmarks.models import Landmark

    return Landmark.objects.create(
        target_id="TestTower",
        name="测试塔",
        lat=10.0,
        lon=20.0,
        intro="测试用百科介绍",
        image_url="/landmarks/TestTower.jpg",
    )


@pytest.fixture
def badges(db):
    from apps.badges.models import Badge

    return [
        Badge.objects.create(
            code="first_footprint",
            name="初次远行",
            category="footprint",
            threshold=1,
            icon="👣",
        ),
        Badge.objects.create(
            code="first_journal",
            name="第一篇手账",
            category="journal",
            threshold=1,
            icon="📔",
        ),
        Badge.objects.create(
            code="first_comment",
            name="破冰发言",
            category="comment",
            threshold=1,
            icon="💬",
        ),
    ]
