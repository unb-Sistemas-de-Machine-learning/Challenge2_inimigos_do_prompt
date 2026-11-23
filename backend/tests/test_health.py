"""Testes básicos de saúde e rotas iniciais da API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_knowledge_status() -> None:
    response = client.get("/api/v1/knowledge/status")
    assert response.status_code == 200
    assert response.json()["status"] == "not_indexed"
