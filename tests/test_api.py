"""
Integration-style tests for the FastAPI endpoints.
These tests mock the service layer to avoid needing a real database.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from ffl.api.main import app

client = TestClient(app)

SAMPLE_LICENSE = {
    "ffl_number": "9-82-005-01-7C-01714",
    "status": "active",
    "expiration_date": "2027-03-31",
    "region": "9",
    "license_type": {
        "code": "01",
        "name": "Dealer",
        "description": "Licensed to buy and sell firearms.",
        "activities": ["sell_firearms", "buy_firearms"],
        "sot_class": None,
    },
    "business": {
        "legal_name": "GEBO INC",
        "dba_name": "ACE HARDWARE & GUN SHOP",
        "phone": "2082328722",
    },
    "address": {
        "street": "222 S FIFTH",
        "city": "POCATELLO",
        "state": "ID",
        "zip": "83201",
        "county": None,
        "latitude": 42.865,
        "longitude": -112.450,
    },
}


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAddressLookup:
    def test_address_lookup_returns_results(self):
        with patch(
            "ffl.api.routers.address_lookup.lookup_by_address",
            new=AsyncMock(return_value=[SAMPLE_LICENSE]),
        ):
            resp = client.get(
                "/api/v1/lookup/address",
                params={"street": "222 S FIFTH", "city": "POCATELLO", "state": "ID", "zip": "83201"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["results"][0]["ffl_number"] == "9-82-005-01-7C-01714"

    def test_address_lookup_empty_results(self):
        with patch(
            "ffl.api.routers.address_lookup.lookup_by_address",
            new=AsyncMock(return_value=[]),
        ):
            resp = client.get(
                "/api/v1/lookup/address",
                params={"street": "999 Unknown Rd", "city": "Nowhere", "state": "ZZ"},
            )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_address_lookup_requires_street(self):
        resp = client.get("/api/v1/lookup/address", params={"city": "Austin", "state": "TX"})
        assert resp.status_code == 422

    def test_address_lookup_requires_city(self):
        resp = client.get("/api/v1/lookup/address", params={"street": "100 Main", "state": "TX"})
        assert resp.status_code == 422

    def test_address_lookup_requires_state(self):
        resp = client.get("/api/v1/lookup/address", params={"street": "100 Main", "city": "Austin"})
        assert resp.status_code == 422

    def test_address_lookup_invalid_zip_length(self):
        resp = client.get(
            "/api/v1/lookup/address",
            params={"street": "100 Main", "city": "Austin", "state": "TX", "zip": "1234"},
        )
        assert resp.status_code == 422


class TestZipLookup:
    def test_zip_lookup_returns_results(self):
        with patch(
            "ffl.api.routers.zip_lookup.lookup_by_zip",
            new=AsyncMock(return_value=[SAMPLE_LICENSE]),
        ):
            resp = client.get("/api/v1/lookup/zip/83201")
        assert resp.status_code == 200
        data = resp.json()
        assert data["zip_code"] == "83201"
        assert data["count"] == 1

    def test_zip_lookup_with_radius(self):
        with patch(
            "ffl.api.routers.zip_lookup.lookup_by_zip",
            new=AsyncMock(return_value=[SAMPLE_LICENSE]),
        ):
            resp = client.get("/api/v1/lookup/zip/83201", params={"radius_miles": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["radius_miles"] == 10.0

    def test_zip_lookup_invalid_zip(self):
        resp = client.get("/api/v1/lookup/zip/1234")
        assert resp.status_code == 422

    def test_zip_lookup_invalid_radius(self):
        resp = client.get("/api/v1/lookup/zip/83201", params={"radius_miles": 9999})
        assert resp.status_code == 422


class TestChangesLookup:
    SAMPLE_CHANGES = {
        "since_date": "2025-01-01",
        "expiring_within_days": 90,
        "recent_changes": [
            {
                "event_type": "inserted",
                "changed_at": "2025-03-15T12:00:00+00:00",
                "license_number": "9-82-005-01-7C-01714",
                "old_data": None,
                "new_data": {"business_name": "GEBO INC"},
            }
        ],
        "upcoming_expirations": [SAMPLE_LICENSE],
    }

    def test_changes_returns_structure(self):
        with patch(
            "ffl.api.routers.changes.lookup_changes",
            new=AsyncMock(return_value=self.SAMPLE_CHANGES),
        ):
            resp = client.get("/api/v1/lookup/changes")
        assert resp.status_code == 200
        data = resp.json()
        assert "recent_changes" in data
        assert "upcoming_expirations" in data
        assert "since_date" in data

    def test_changes_with_since_date(self):
        with patch(
            "ffl.api.routers.changes.lookup_changes",
            new=AsyncMock(return_value=self.SAMPLE_CHANGES),
        ):
            resp = client.get("/api/v1/lookup/changes", params={"since_date": "2025-01-01"})
        assert resp.status_code == 200

    def test_changes_invalid_date(self):
        resp = client.get("/api/v1/lookup/changes", params={"since_date": "not-a-date"})
        assert resp.status_code == 422

    def test_changes_invalid_days(self):
        resp = client.get("/api/v1/lookup/changes", params={"expiring_within_days": -1})
        assert resp.status_code == 422
