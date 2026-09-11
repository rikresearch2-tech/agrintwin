"""
Integration tests for the core AgriN Twin pipeline: farmer -> plot ->
sensor + satellite + disease + soil score -> twin summary -> voice agent.

Run with: pytest -v  (from the backend/ directory)
"""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.database import Base, engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _make_image_bytes(color) -> bytes:
    img = Image.new("RGB", (100, 100), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_full_plot_lifecycle():
    # 1. create farmer
    resp = client.post(
        "/api/v1/farmers",
        json={"name": "Test Farmer", "phone_number": "+91-9999999999", "preferred_language": "bn", "nation": "IN"},
    )
    assert resp.status_code == 201
    farmer = resp.json()

    # 2. create plot
    resp = client.post(
        "/api/v1/plots",
        json={
            "farmer_id": farmer["id"],
            "name": "Test Plot",
            "latitude": 22.0,
            "longitude": 88.0,
            "area_hectares": 1.0,
            "primary_crop": "rice",
            "nation": "IN",
        },
    )
    assert resp.status_code == 201
    plot = resp.json()
    plot_id = plot["id"]

    # 3. ingest a sensor reading
    resp = client.post(
        "/api/v1/sensor-readings",
        headers={"X-Pod-Api-Key": "dev-pod-key-change-in-prod"},
        json={
            "plot_id": plot_id,
            "soil_moisture_pct": 35.0,
            "soil_temp_c": 26.0,
            "air_temp_c": 30.0,
            "air_humidity_pct": 70.0,
            "soil_conductivity_us_cm": 450.0,
        },
    )
    assert resp.status_code == 201

    # 3b. wrong key is rejected
    resp = client.post(
        "/api/v1/sensor-readings",
        headers={"X-Pod-Api-Key": "wrong-key"},
        json={
            "plot_id": plot_id,
            "soil_moisture_pct": 35.0,
            "soil_temp_c": 26.0,
            "air_temp_c": 30.0,
            "air_humidity_pct": 70.0,
            "soil_conductivity_us_cm": 450.0,
        },
    )
    assert resp.status_code == 401

    # 4. refresh satellite snapshot
    resp = client.post(f"/api/v1/plots/{plot_id}/satellite/refresh")
    assert resp.status_code == 201
    assert -1.0 <= resp.json()["ndvi"] <= 1.0

    # 5. disease scan — green image should be classified healthy
    green_bytes = _make_image_bytes((40, 160, 40))
    resp = client.post(
        f"/api/v1/plots/{plot_id}/disease-scan",
        files={"image": ("leaf.jpg", green_bytes, "image/jpeg")},
    )
    assert resp.status_code == 201
    assert resp.json()["is_healthy"] is True

    # 6. brown image should be classified as a disease
    brown_bytes = _make_image_bytes((150, 110, 40))
    resp = client.post(
        f"/api/v1/plots/{plot_id}/disease-scan",
        files={"image": ("leaf2.jpg", brown_bytes, "image/jpeg")},
    )
    assert resp.status_code == 201
    assert resp.json()["is_healthy"] is False

    # 7. compute soil health score
    resp = client.post(f"/api/v1/plots/{plot_id}/soil-score/compute")
    assert resp.status_code == 201
    score = resp.json()["score"]
    assert 0 <= score <= 100

    # 8. full twin summary is fused correctly
    resp = client.get(f"/api/v1/plots/{plot_id}/twin")
    assert resp.status_code == 200
    twin = resp.json()
    assert twin["latest_sensor"] is not None
    assert twin["latest_satellite"] is not None
    assert twin["latest_disease_report"] is not None
    assert twin["latest_soil_score"] is not None

    # 9. voice agent answers grounded in the twin data (rule-based fallback, no API key needed)
    resp = client.post(
        "/api/v1/voice/query",
        json={"plot_id": plot_id, "language": "bn", "transcript": "amar mati kemon ache?", "channel": "ivr"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "soil_health_query"
    assert str(score) in body["response_text"] or "score" in body["response_text"].lower()


def test_federation_publish_and_status():
    resp = client.post(
        "/api/v1/federation/updates",
        json={
            "node_id": "TEST-NODE",
            "nation": "IN",
            "model_name": "disease-classifier",
            "model_version": "v0.0-test",
            "training_sample_count": 100,
            "eval_metric_name": "f1_macro",
            "eval_metric_value": 0.8,
        },
    )
    assert resp.status_code == 201

    resp = client.get("/api/v1/federation/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert any(n["node_id"] == "TEST-NODE" for n in nodes)


def test_unknown_plot_404():
    resp = client.get("/api/v1/plots/does-not-exist/twin")
    assert resp.status_code == 404
