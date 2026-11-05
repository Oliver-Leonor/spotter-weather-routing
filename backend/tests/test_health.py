import json

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
    assert response["Content-Type"] == "application/json"
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "No API route matches /api/does-not-exist/."}
    }


def test_unknown_non_api_path_is_404_json(client):
    response = client.get("/")
    assert response.status_code == 404
    assert response["Content-Type"] == "application/json"
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_server_error_handler_returns_json_envelope():
    from django.test import RequestFactory
    from django.urls import get_callable

    from config.urls import handler500

    response = get_callable(handler500)(RequestFactory().get("/api/health/"))
    assert response.status_code == 500
    assert response["Content-Type"] == "application/json"
    assert json.loads(response.content) == {
        "error": {"code": "SERVER_ERROR", "message": "An unexpected error occurred."}
    }
