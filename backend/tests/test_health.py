from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint_is_available_without_gemini_key():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_endpoint_is_available_without_gemini_key():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_cors_preflight_for_local_frontend():
    response = client.options(
        "/research/run",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
