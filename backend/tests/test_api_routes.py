"""Testes das rotas da API REST, privacidade local e HTTPS em produção (Issue #8)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_chat_endpoint_retorna_evidencias_e_header_privacidade() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"question": "Qual a altura ideal do monitor na NR-17?", "top_k": 3},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Webcam-Processing") == "local-only"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    data = resp.json()
    assert data["grounded"] is True
    assert len(data["evidence"]) >= 1


def test_recommendations_para_posture_event_sem_video() -> None:
    client = TestClient(app)
    payload = {
        "event_id": str(uuid4()),
        "timestamp": "2026-11-26T22:00:00Z",
        "camera_mode": "frontal",
        "landmarks_confidence": 0.92,
        "duration_minutes": 3.5,
        "features": {
            "head_forward_offset": 0.25,
            "trunk_inclination": 0.08,
            "shoulder_asymmetry": 0.03,
            "apparent_face_scale": 0.18,
        },
        "classification": {
            "label": "FORWARD_HEAD",
            "confidence": 0.88,
        },
    }
    resp = client.post("/api/v1/recommendations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "FORWARD_HEAD"
    assert data["local_alerts_independent"] is True
    assert data["safety"]["approved"] is True
    assert len(data["evidence"]) >= 1


def test_knowledge_status_reporta_corpus_disponivel() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/knowledge/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["corpus_chunks"] == 507
    assert data["retrieval_mode"] in {"bm25_corpus", "hybrid_chroma_bm25"}


def test_https_enforcement_em_producao(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        resp_http = client.get("/health", follow_redirects=False)
        assert resp_http.status_code == 307
        assert resp_http.headers["location"].startswith("https://")

        resp_https = client.get("/health", headers={"X-Forwarded-Proto": "https"})
        assert resp_https.status_code == 200
        assert "Strict-Transport-Security" in resp_https.headers
    finally:
        get_settings.cache_clear()
