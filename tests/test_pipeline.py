from datetime import datetime
from pathlib import Path

from madrigal_assistant.models import RawEvent
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
