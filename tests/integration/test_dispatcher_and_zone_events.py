"""
Integration tests for the dispatcher → audit log path and the
zone activate/deactivate event hooks (GitHub issue #51).

These tests use the REAL AuditLogRepository (not a MagicMock) so they
catch signature mismatches between the dispatcher and the repository.
"""

from __future__ import annotations

import pytest
import mongomock
import mongoengine
from bson import ObjectId
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_dispatcher",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect_all()


@pytest.fixture(autouse=True)
def restore_real_audit_repo(mock_db):
    """
    The other test modules in this suite swap dispatcher._audit_repo for a
    MagicMock at session scope. Force the real repository back in for the
    duration of these tests, then restore whatever was there before.
    """
    from src.core.events.dispatcher import dispatcher
    from src.infrastructure.repositories.audit_log_repository import (
        AuditLogRepository,
    )

    previous = dispatcher._audit_repo
    dispatcher._audit_repo = AuditLogRepository()
    yield
    dispatcher._audit_repo = previous


@pytest.fixture(autouse=True)
def clean_collections(mock_db):
    from src.models.audit_log import AuditLog
    from src.models.zone import Zone

    AuditLog.drop_collection()
    Zone.drop_collection()


@pytest.fixture(scope="session")
def client(mock_db):
    with patch("src.main.init_db"), patch("src.main.close_db"):
        from src.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


ZONE_PAYLOAD = {
    "name": "Audit-trail eco zone",
    "zone_type": "eco",
    "status": "active",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [10.0, 30.0],
            [20.0, 30.0],
            [20.0, 40.0],
            [10.0, 40.0],
            [10.0, 30.0],
        ]],
    },
}


class TestDispatcherAuditLog:
    """The dispatcher writes exactly one audit log per event and survives
    bad entity ids."""

    def test_dispatch_writes_exactly_one_audit_log(self):
        from src.core.events.dispatcher import dispatcher
        from src.core.events.event import Event
        from src.models.audit_log import AuditLog

        zone_oid = str(ObjectId())
        dispatcher.dispatch(
            Event(
                event_type="ZONE_STATUS_CHANGED",
                data={"zone_id": zone_oid, "new_status": "inactive"},
            )
        )

        logs = list(AuditLog.objects(event_type="ZONE_STATUS_CHANGED"))
        assert len(logs) == 1, "dispatcher must not double-write audit log"
        assert str(logs[0].entity_id) == zone_oid
        assert logs[0].entity_type == "zone"
        assert logs[0].data["new_status"] == "inactive"

    def test_dispatch_tolerates_non_objectid_entity_id(self):
        """Some event sources pass non-ObjectId strings — the audit row
        should still be written, just without an entity_id."""
        from src.core.events.dispatcher import dispatcher
        from src.core.events.event import Event
        from src.models.audit_log import AuditLog

        dispatcher.dispatch(
            Event(
                event_type="ZONE_STATUS_CHANGED",
                data={"zone_id": "not-an-objectid", "new_status": "active"},
            )
        )

        logs = list(AuditLog.objects(event_type="ZONE_STATUS_CHANGED"))
        assert len(logs) == 1
        assert logs[0].entity_id is None
        assert logs[0].entity_type == "zone"

    def test_dispatch_with_vessel_id_sets_entity_type_vessel(self):
        from src.core.events.dispatcher import dispatcher
        from src.core.events.event import Event
        from src.models.audit_log import AuditLog

        vessel_oid = str(ObjectId())
        dispatcher.dispatch(
            Event(
                event_type="VESSEL_ANOMALY",
                data={"vessel_id": vessel_oid, "kind": "speed_deviation"},
            )
        )

        log = AuditLog.objects(event_type="VESSEL_ANOMALY").first()
        assert log is not None
        assert log.entity_type == "vessel"
        assert str(log.entity_id) == vessel_oid


class TestZoneActivateDeactivateEvents:
    """Issue #51: activating or deactivating a zone fires
    ZONE_STATUS_CHANGED and persists an audit log entry."""

    def _create_zone(self, client) -> str:
        resp = client.post("/api/v1/zones/", json=ZONE_PAYLOAD)
        assert resp.status_code in (200, 201), resp.text
        body = resp.json()
        # mongoengine to_json embeds the id under "_id": {"$oid": "..."}
        return body["_id"]["$oid"] if isinstance(body.get("_id"), dict) else body["_id"]

    def test_deactivate_fires_event_and_writes_audit_log(self, client):
        from src.models.audit_log import AuditLog

        zone_id = self._create_zone(client)
        resp = client.post(f"/api/v1/zones/{zone_id}/deactivate")
        assert resp.status_code == 200

        log = AuditLog.objects(event_type="ZONE_STATUS_CHANGED").first()
        assert log is not None, "ZONE_STATUS_CHANGED audit log was not written"
        assert log.entity_type == "zone"
        assert str(log.entity_id) == zone_id
        assert log.data["new_status"] == "inactive"

    def test_activate_fires_event_and_writes_audit_log(self, client):
        from src.models.audit_log import AuditLog

        zone_id = self._create_zone(client)
        # first deactivate so activate represents a real state change
        client.post(f"/api/v1/zones/{zone_id}/deactivate")
        AuditLog.drop_collection()  # only assert on the activate event

        resp = client.post(f"/api/v1/zones/{zone_id}/activate")
        assert resp.status_code == 200

        log = AuditLog.objects(event_type="ZONE_STATUS_CHANGED").first()
        assert log is not None
        assert log.data["new_status"] == "active"

    def test_404_path_does_not_write_audit_log(self, client):
        from src.models.audit_log import AuditLog

        fake_id = str(ObjectId())
        resp = client.post(f"/api/v1/zones/{fake_id}/activate")
        assert resp.status_code == 404
        assert AuditLog.objects(event_type="ZONE_STATUS_CHANGED").count() == 0
