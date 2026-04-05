from pathlib import Path

from fastapi.testclient import TestClient

from madrigal_assistant.api.app import create_app
from madrigal_assistant.models import RawEvent
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


def test_api_metadata_includes_pyrogram_status(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-metadata.db")
    client = TestClient(create_app(service))

    response = client.get("/api/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert "pyrogram" in payload
    assert "installed" in payload["pyrogram"]
    assert "api_id_configured" in payload["pyrogram"]
    assert "chat" in payload
    assert "provider" in payload["chat"]


def test_api_chat_creates_session_and_returns_sources(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-chat.db")
    client = TestClient(create_app(service))
    service.import_seed()
    user = service.db.create_user("chat-user@example.com", "hash")
    assert user

    response = client.post(
        "/api/chat/ask",
        json={
            "user_id": user["id"],
            "message": "Что происходит в Таганроге и какие темы сейчас важные?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["id"] > 0
    assert payload["assistant_message"]["content"]
    assert payload["assistant_message"]["citations"]
    assert payload["status"]["retrieval_enabled"] is True


def test_api_chat_sessions_return_history(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-chat-history.db")
    client = TestClient(create_app(service))
    service.import_seed()
    user = service.db.create_user("chat-history@example.com", "hash")
    assert user

    ask_response = client.post(
        "/api/chat/ask",
        json={
            "user_id": user["id"],
            "message": "Есть ли проблемы по ЖКХ за последние дни?",
        },
    )
    assert ask_response.status_code == 200
    session_id = ask_response.json()["session"]["id"]

    sessions_response = client.get(f"/api/chat/sessions?user_id={user['id']}")
    assert sessions_response.status_code == 200
    assert sessions_response.json()["items"]

    detail_response = client.get(f"/api/chat/sessions/{session_id}?user_id={user['id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert len(detail_payload["messages"]) >= 2
    assert detail_payload["messages"][0]["role"] == "user"


def test_chat_retrieval_prefers_requested_municipality(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-chat-retrieval.db")
    service.import_seed()

    contexts = service._retrieve_chat_context("Что сейчас происходит в Таганроге и какие темы подтверждены официально?")

    assert contexts
    assert contexts[0]["municipality"] == "Таганрог"


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


def test_frontend_snapshot_prioritizes_recent_topics(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "api-freshness.db")
    latest_seen = RawEvent.model_validate(
        {
            "event_id": "seed-latest",
            "url": "https://demo.local/latest",
            "source_type": "media",
            "source_name": "Новости",
            "published_at": "2026-04-05T02:20:00+03:00",
            "title": "latest",
            "text": "latest",
        }
    ).published_at
    recent_topic = {
        "id": "topic-recent",
        "municipality": "Азов",
        "priority": "Высокий",
        "score": 24,
        "officialSignal": True,
        "updatedAt": "2026-04-05T02:10:00+03:00",
        "rank": 9,
    }
    stale_topic = {
        "id": "topic-stale",
        "municipality": "Ростов-на-Дону",
        "priority": "Средний",
        "score": 31,
        "officialSignal": False,
        "updatedAt": "2026-04-01T10:00:00+03:00",
        "rank": 1,
    }

    ordered = service._rerank_frontend_topics(
        service._merge_frontend_topics(
            service._sort_frontend_topics([recent_topic], latest_seen),
            service._sort_frontend_topics([stale_topic], latest_seen),
        )
    )

    assert ordered[0]["municipality"] == "Азов"
    assert ordered[0]["rank"] == 1
    assert ordered[1]["municipality"] == "Ростов-на-Дону"
