from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theshed.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_health_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("THESHED_REF", raising=False)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ref": "unknown"}


def test_health_reports_the_install_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THESHED_REF", "cursor/health-install-ref-8f92")
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "ref": "cursor/health-install-ref-8f92",
    }


def test_health_route_is_registered_before_static_mount() -> None:
    text = (ROOT / "src" / "theshed" / "main.py").read_text()
    assert text.index('@app.get("/health")') < text.index('app.mount("/",')
