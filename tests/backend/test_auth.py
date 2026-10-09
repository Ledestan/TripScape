"""健康检查 + 认证 + 权限测试。"""


class TestHealth:
    def test_healthz(self, api_client):
        r = api_client.json_get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_readyz(self, api_client, db):
        r = api_client.json_get("/readyz")
        assert r.status_code == 200
        assert r.json()["checks"]["mysql"] == "ok"


class TestAuth:
    def test_register_and_login(self, api_client, db):
        r = api_client.json_post(
            "/api/auth/register", {"username": "newuser", "password": "pass123456"}
        )
        assert r.status_code == 200
        assert r.json()["token"]

        r = api_client.json_post(
            "/api/auth/login", {"username": "newuser", "password": "pass123456"}
        )
        assert r.status_code == 200

    def test_register_short_password_rejected(self, api_client, db):
        r = api_client.json_post(
            "/api/auth/register", {"username": "x1", "password": "123"}
        )
        assert r.status_code == 400

    def test_login_wrong_password(self, api_client, user):
        r = api_client.json_post(
            "/api/auth/login", {"username": "tester", "password": "wrong-password"}
        )
        assert r.status_code == 400

    def test_me_requires_login(self, api_client):
        r = api_client.json_get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, api_client, user, user_token):
        r = api_client.json_get("/api/auth/me", token=user_token)
        assert r.status_code == 200
        assert r.json()["username"] == "tester"


class TestAdminGuard:
    def test_normal_user_forbidden(self, api_client, user, user_token):
        r = api_client.json_get("/api/admin/review/journals", token=user_token)
        assert r.status_code == 403

    def test_admin_login_rejects_normal_user(self, api_client, user):
        r = api_client.json_post(
            "/api/admin/login", {"username": "tester", "password": "pass123456"}
        )
        assert r.status_code == 403

    def test_admin_can_access(self, api_client, admin_token):
        r = api_client.json_get("/api/admin/review/journals", token=admin_token)
        assert r.status_code == 200
