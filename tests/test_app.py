from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_generate_fixture_deterministico():
    r = client.post("/generate", json={"prompt": "ola mundo"})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "fixture-1"
    assert body["usage"]["prompt_tokens"] >= 1
    assert body["latency_ms"] > 0
    assert body["estimated_cost_usd"] >= 0
    # determinismo: mesmo prompt -> mesmo texto
    r2 = client.post("/generate", json={"prompt": "ola mundo"})
    assert r2.json()["text"] == body["text"]


def test_generate_rejeita_prompt_vazio():
    r = client.post("/generate", json={"prompt": ""})
    assert r.status_code == 422


def test_metrics_expoe_contadores():
    client.post("/generate", json={"prompt": "aquecer metrica"})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "llmops_requests_total" in r.text
    assert "llmops_request_latency_seconds" in r.text
    assert "llmops_estimated_cost_usd_total" in r.text
