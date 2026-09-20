from pathlib import Path

from fastapi.testclient import TestClient

from theshed.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_route_is_registered_before_static_mount() -> None:
    text = (ROOT / "src" / "theshed" / "main.py").read_text()
    assert text.index('@app.get("/health")') < text.index('app.mount("/",')
