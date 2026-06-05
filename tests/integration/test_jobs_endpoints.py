"""
Integration tests for the admin job-queue endpoints (#85).
"""

import time

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
def clean_users_and_queue():
    from src.models.user import User
    from src.infrastructure.queue.task_queue import _default_queue

    User.drop_collection()
    if _default_queue is not None:
        with _default_queue._lock:
            _default_queue._jobs.clear()
            _default_queue._futures.clear()
    yield


@pytest.fixture
def admin_token(client) -> str:
    company_id = str(ObjectId())
    client.post("/api/v1/auth/bootstrap-admin", json={
        "company_id": company_id,
        "email": "admin@x.com",
        "password": "supersecret123",
        "role": "admin",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "admin@x.com", "password": "supersecret123",
    })
    return login.json()["access_token"]


@pytest.fixture
def viewer_token(client) -> str:
    company_id = str(ObjectId())
    # Bootstrap an admin first so we can have the admin create a viewer.
    client.post("/api/v1/auth/bootstrap-admin", json={
        "company_id": company_id, "email": "a@x.com",
        "password": "supersecret123", "role": "admin",
    })
    admin = client.post("/api/v1/auth/login", json={
        "email": "a@x.com", "password": "supersecret123",
    }).json()["access_token"]
    client.post(
        "/api/v1/auth/register",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "company_id": company_id, "email": "v@x.com",
            "password": "supersecret123", "role": "viewer",
        },
    )
    viewer = client.post("/api/v1/auth/login", json={
        "email": "v@x.com", "password": "supersecret123",
    }).json()["access_token"]
    return viewer


def test_list_jobs_requires_admin(client, viewer_token):
    resp = client.get(
        "/api/v1/jobs/",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_enqueue_unknown_job_returns_404(client, admin_token):
    resp = client.post(
        "/api/v1/jobs/not_a_real_job",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert resp.status_code == 404


def test_enqueue_registered_job_executes(client, admin_token):
    # Register a one-off test job onto the default queue.
    from src.infrastructure.queue import get_default_queue, JobStatus

    queue = get_default_queue()
    queue.register("test_echo", lambda value: value)

    resp = client.post(
        "/api/v1/jobs/test_echo",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": "ping"},
    )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    finished = queue.wait_for(job_id, timeout=2.0)
    assert finished.status == JobStatus.COMPLETED
    assert finished.result == "ping"

    get_resp = client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "completed"
    assert get_resp.json()["result"] == "ping"


def test_get_unknown_job_returns_404(client, admin_token):
    resp = client.get(
        "/api/v1/jobs/nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
