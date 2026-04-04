from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from madrigal_assistant.api.app import create_app
from madrigal_assistant.models import RawEvent
from madrigal_assistant.services import RegionalPulseService


class FakeEmbeddingService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, ...]] = {}

    def encode_texts(self, texts: list[str]) -> list[tuple[float, ...] | None]:
        vectors: list[tuple[float, ...] | None] = []
        for text in texts:
            normalized = (text or "").lower()
            if any(marker in normalized for marker in ("поликли", "терапевт", "врач", "регистрат", "пациент", "медучреж")):
                vector = (1.0, 0.0, 0.0)
            elif any(marker in normalized for marker in ("мусор", "контейнер", "свалк")):
                vector = (0.0, 1.0, 0.0)
            elif any(marker in normalized for marker in ("автобус", "маршрут", "транспорт")):
                vector = (0.0, 0.0, 1.0)
            else:
                vector = (0.5, 0.5, 0.5)
            self._cache[text] = vector
            vectors.append(vector)
        return vectors

    @staticmethod
    def cosine_similarity(left: tuple[float, ...] | None, right: tuple[float, ...] | None) -> float:
        if not left or not right:
            return 0.0
        return sum(a * b for a, b in zip(left, right))

    def status(self):
        class _Status:
            def as_dict(self_inner) -> dict[str, object]:
                return {
                    "enabled": True,
                    "available": True,
                    "active": True,
                    "backend": "fake-test",
                    "model_name": "fake-test-model",
                    "device": "cpu",
                    "cache_size": len(self._cache),
                    "error": None,
                }

        return _Status()


def build_service(tmp_path: Path) -> RegionalPulseService:
    return RegionalPulseService(db_path=tmp_path / "embedding.db", embedding_service=FakeEmbeddingService())


def test_semantic_layer_merges_related_healthcare_posts(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="health-1",
                url="https://demo.local/health-1",
                source_type="social",
                source_name="Telegram / Таганрог",
                published_at=datetime.fromisoformat("2026-04-03T09:10:00+03:00"),
                title="В поликлинике №2 в Таганроге снова огромная очередь",
                text="Жители пишут, что у регистратуры приходится ждать больше часа.",
                municipality="Таганрог",
                is_official=False,
            ),
            RawEvent(
                event_id="health-2",
                url="https://demo.local/health-2",
                source_type="media",
                source_name="Городское медиа",
                published_at=datetime.fromisoformat("2026-04-03T10:00:00+03:00"),
                title="Пациенты не могут быстро попасть к терапевту в медучреждении Таганрога",
                text="Горожане жалуются, что запись к врачу и прием затягиваются.",
                municipality="Таганрог",
                is_official=False,
            ),
        ]
    )

    issues = service.get_top_issues(limit=10).items
    healthcare_topics = [item.topic for item in issues if item.topic.sector == "Здравоохранение"]
    assert healthcare_topics
    assert any(topic.event_count == 2 for topic in healthcare_topics)


def test_api_similar_topics_returns_semantic_matches(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="topic-a",
                url="https://demo.local/topic-a",
                source_type="social",
                source_name="Telegram / Ростов",
                published_at=datetime.fromisoformat("2026-04-03T08:10:00+03:00"),
                title="Очередь в поликлинике на Северном",
                text="Пациенты жалуются на запись к врачу и длинную очередь у кабинета.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
            RawEvent(
                event_id="topic-b",
                url="https://demo.local/topic-b",
                source_type="media",
                source_name="Новочеркасск медиа",
                published_at=datetime.fromisoformat("2026-04-03T09:20:00+03:00"),
                title="Жители Новочеркасска жалуются на перегруженную регистратуру",
                text="В медучреждении сложно попасть к терапевту, горожане ждут приема по несколько часов.",
                municipality="Новочеркасск",
                is_official=False,
            ),
            RawEvent(
                event_id="topic-c",
                url="https://demo.local/topic-c",
                source_type="social",
                source_name="VK / ЖКХ",
                published_at=datetime.fromisoformat("2026-04-03T09:40:00+03:00"),
                title="Во дворе переполнены мусорные контейнеры",
                text="Жители жалуются на невывоз мусора и неприятный запах.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
        ]
    )

    client = TestClient(create_app(service))
    response = client.get("/api/similar-topics", params={"q": "очередь к врачу в поликлинике", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["embedding_layer"]["backend"] == "fake-test"
    assert payload["items"][0]["sector"] == "Здравоохранение"
    assert payload["items"][0]["similarity"] >= 0.6
