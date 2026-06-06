"""
Integration tests for JWT auth + RBAC (#89).
"""

import pytest
import mongomock
import mongoengine
from bson import ObjectId
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect_all()


@pytest.fixture(scope="session")
def client(mock_db):
    from src.core.events.dispatcher import dispatcher
    dispatcher._audit_repo = MagicMock()

    with patch("src.main.init_db"), patch("src.main.close_db"):
        from src.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture(autouse=True)
def clean_users():
    from src.models.user import User
    User.drop_collection()


@pytest.fixture
def company_id() -> str:
    return str(ObjectId())


def _register_admin(client, company_id, email="admin@example.com") -> str:
    """Bootstrap an admin and return their access token."""
    client.post(
        "/api/v1/auth/bootstrap-admin",
        json={
            "company_id": company_id,
            "email": email,
            "password": "supersecret123",
            "full_name": "Admin",
            "role": "admin",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


class TestBootstrapAndLogin:
    def test_bootstrap_creates_first_admin(self, client, company_id):
        resp = client.post("/api/v1/auth/bootstrap-admin", json={
            "company_id": company_id,
            "email": "first@x.com",
            "password": "supersecret123",
            "role": "admin",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_bootstrap_blocked_once_users_exist(self, client, company_id):
        _register_admin(client, company_id)
        resp = client.post("/api/v1/auth/bootstrap-admin", json={
            "company_id": company_id,
            "email": "second@x.com",
            "password": "supersecret123",
            "role": "admin",
        })
        assert resp.status_code == 409

    def test_login_returns_jwt(self, client, company_id):
        token = _register_admin(client, company_id)
        assert token.count(".") == 2  # header.payload.signature

    def test_login_wrong_password_returns_401(self, client, company_id):
        _register_admin(client, company_id)
        resp = client.post("/api/v1/auth/login", json={
            "email": "admin@example.com", "password": "wrong",
        })
        assert resp.status_code == 401


class TestMeAndRoles:
    def test_me_requires_bearer_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_returns_current_user(self, client, company_id):
        token = _register_admin(client, company_id)
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "admin@example.com"
        assert body["role"] == "admin"

    def test_register_requires_admin(self, client, company_id):
        admin_token = _register_admin(client, company_id)
        # Create a viewer via admin
        viewer_resp = client.post(
            "/api/v1/auth/register",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "company_id": company_id,
                "email": "viewer@example.com",
                "password": "supersecret123",
                "role": "viewer",
            },
        )
        assert viewer_resp.status_code == 200

        # Log in as viewer
        viewer_token = client.post("/api/v1/auth/login", json={
            "email": "viewer@example.com", "password": "supersecret123",
        }).json()["access_token"]

        # Viewer trying to register another user → 403
        forbidden = client.post(
            "/api/v1/auth/register",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "company_id": company_id,
                "email": "third@example.com",
                "password": "supersecret123",
                "role": "viewer",
            },
        )
        assert forbidden.status_code == 403

    def test_admin_cannot_register_in_other_company(self, client, company_id):
        admin_token = _register_admin(client, company_id)
        other_company_id = str(ObjectId())
        resp = client.post(
            "/api/v1/auth/register",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "company_id": other_company_id,
                "email": "cross-tenant@example.com",
                "password": "supersecret123",
                "role": "admin",
            },
        )
        assert resp.status_code == 403

    def test_bad_bearer_format_is_401(self, client, company_id):
        token = _register_admin(client, company_id)
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": token},  # missing "Bearer "
        )
        assert resp.status_code == 401


class TestPasswordPolicy:
    def test_short_password_rejected_on_bootstrap(self, client, company_id):
        resp = client.post("/api/v1/auth/bootstrap-admin", json={
            "company_id": company_id,
            "email": "short@x.com",
            "password": "short12",  # 7 chars
            "role": "admin",
        })
        assert resp.status_code == 422

    def test_eleven_char_password_still_rejected(self, client, company_id):
        # Boundary: must be at least 12 characters.
        resp = client.post("/api/v1/auth/bootstrap-admin", json={
            "company_id": company_id,
            "email": "boundary@x.com",
            "password": "elevenchars",  # 11 chars
            "role": "admin",
        })
        assert resp.status_code == 422


class TestJWTSecretCheck:
    def test_check_passes_in_development(self, monkeypatch):
        from src.main import _check_jwt_secret
        from src.core.config import settings

        monkeypatch.setattr(settings, "APP_ENV", "development")
        monkeypatch.setattr(settings, "JWT_SECRET", "dev-only-jwt-secret-anything")
        _check_jwt_secret()  # no raise

    def test_check_raises_when_default_secret_in_production(self, monkeypatch):
        import pytest

        from src.main import _check_jwt_secret
        from src.core.config import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "JWT_SECRET", "dev-only-jwt-secret-please-replace")
        with pytest.raises(RuntimeError, match="placeholder"):
            _check_jwt_secret()

    def test_check_passes_when_real_secret_in_production(self, monkeypatch):
        from src.main import _check_jwt_secret
        from src.core.config import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(
            settings,
            "JWT_SECRET",
            "a-real-long-secret-set-by-the-operator-1234567890",
        )
        _check_jwt_secret()  # no raise
