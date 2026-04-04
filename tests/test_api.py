from pathlib import Path

from fastapi.testclient import TestClient

from madrigal_assistant.api.app import create_app
from madrigal_assistant.services import RegionalPulseService


def test_api_seed_and_top_issues(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api.db")
    client = TestClient(create_app(service))

    seed_response = client.post("/api/import/seed")
    assert seed_response.status_code == 200
    assert seed_response.json()["imported"] >= 20

    top_response = client.get("/api/top-issues")
    assert top_response.status_code == 200
    payload = top_response.json()
    assert payload["total_topics"] >= 8
    assert 1 <= len(payload["items"]) <= 10

    cards_response = client.get("/api/problem-cards")
    assert cards_response.status_code == 200
    cards_payload = cards_response.json()
    assert cards_payload["items"]
    assert "urgency" in cards_payload["items"][0]
    assert "source_mix" in cards_payload["items"][0]
    assert "trend" in cards_payload["items"][0]
    assert "confidence" in cards_payload["items"][0]
    assert "timeline" in cards_payload["items"][0]


def test_api_manual_import_accepts_csv(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-manual.db")
    client = TestClient(create_app(service))

    csv_payload = (
        "source_name,date,message,municipality,url\n"
        "VK / Test,2026-04-03T12:30:00+03:00,Жители жалуются на яму у школы,Ростов-на-Дону,https://vk.com/wall-1_1\n"
    )
    response = client.post(
        "/api/import/manual",
        files={"file": ("vk_dump.csv", csv_payload.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1


def test_api_frontend_snapshot_returns_dashboard_shape(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-frontend.db")
    client = TestClient(create_app(service))

    client.post("/api/import/seed")
    response = client.get("/api/frontend-snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["regionName"]
    assert "topProblems" in payload
    assert "topics" in payload
    assert "municipalities" in payload
    assert "trends" in payload
    assert {"24h", "7d", "30d"} <= set(payload["trends"])
    if payload["topProblems"]:
        first = payload["topProblems"][0]
        assert "whyTop" in first
        assert "sources" in first
        assert "factors" in first


def test_api_refresh_status_returns_scheduler_metadata(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-refresh.db")
    client = TestClient(create_app(service))

    response = client.get("/api/refresh-status")

    assert response.status_code == 200
    payload = response.json()
    assert "enabled" in payload
    assert "intervalSeconds" in payload
    assert "maxPerSource" in payload
    assert "running" in payload


def test_api_serves_built_frontend_when_dist_exists(tmp_path: Path, monkeypatch) -> None:
    frontend_dist = tmp_path / "dist"
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("<html><body>frontend ok</body></html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok')", encoding="utf-8")

    monkeypatch.setenv("MADRIGAL_FRONTEND_DIST_PATH", str(frontend_dist))

    service = RegionalPulseService(db_path=tmp_path / "api-frontend-static.db")
    client = TestClient(create_app(service))

    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "frontend ok" in root_response.text

    asset_response = client.get("/assets/app.js")
    assert asset_response.status_code == 200
    assert "console.log('ok')" in asset_response.text
