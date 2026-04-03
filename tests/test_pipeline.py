from datetime import datetime
from pathlib import Path

from madrigal_assistant.models import RawEvent
from madrigal_assistant.settings import load_region_config
from madrigal_assistant.services import RegionalPulseService


def build_service(tmp_path: Path) -> RegionalPulseService:
    return RegionalPulseService(db_path=tmp_path / "test.db")


def test_seed_builds_top_issues(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    result = service.import_seed()
    assert result.imported >= 20

    snapshot = service.get_top_issues()
    assert snapshot.total_topics >= 8
    assert len(snapshot.items) == 10


def test_bot_penalty_and_contradiction_are_detected(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.import_seed()
    snapshot = service.get_top_issues()

    noisy_topics = [item.topic for item in snapshot.items if "мусор" in item.topic.label.lower()]
    assert noisy_topics
    assert noisy_topics[0].bot_score >= 0.5

    contradictions = [item.topic for item in snapshot.items if item.topic.contradiction_flag]
    assert contradictions


def test_unknown_municipality_is_preserved(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="unknown-muni",
                url="https://demo.seed/custom/unknown",
                source_type="social",
                source_name="Telegram / Test",
                published_at=datetime.fromisoformat("2026-04-03T10:00:00+03:00"),
                title="Жители пожаловались на странный запах без геометки",
                text="Поступили жалобы на запах, но место не уточняется и привязка к району отсутствует.",
                municipality=None,
                is_official=False,
            )
        ]
    )
    snapshot = service.get_top_issues()
    unknown_topics = [item.topic for item in snapshot.items if "unknown" in item.topic.municipalities]
    assert unknown_topics


def test_manual_csv_import_normalizes_alias_columns(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    csv_payload = (
        "source,created_at,message,city,link,official,views\n"
        "MAX / районный чат,2026-04-03T09:30:00+03:00,Жители пишут про запах гари,Батайск,https://max.example/post/1,false,1450\n"
    ).encode("utf-8")

    result = service.import_manual(csv_payload, "max_dump.csv")
    assert result.imported == 1

    events = service.get_raw_events().items
    assert len(events) == 1
    assert events[0].source_type == "social"
    assert events[0].municipality == "Батайск"
    assert events[0].engagement == 1450


def test_region_config_builds_live_sources_from_catalog() -> None:
    config = load_region_config()
    source_ids = {item["id"] for item in config["sources"]}

    assert "don24_rss" in source_ids
    assert "telegram_don24tv" in source_ids
    assert "donnews_site" not in source_ids
    assert "max_public_chats_manual" not in source_ids
