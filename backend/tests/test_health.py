import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


def test_health_endpoint_reports_ok_and_providers(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["providers"] == {"routing": "valhalla", "weather": "open-meteo"}
    assert isinstance(body["version"], str) and body["version"]


def test_unknown_api_route_is_404_json(client):
    response = client.get("/api/does-not-exist/")
    assert response.status_code == 404
