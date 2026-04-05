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
    assert 1 <= len(snapshot.items) <= 10


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


def test_problem_cards_are_frontend_ready(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.import_seed()

    cards = service.get_problem_cards()
    assert cards.items
    first = cards.items[0]
    assert first.rank == 1
    assert first.why_now
    assert first.key_facts
    assert first.primary_municipality
    assert first.trend in {"rising", "stable", "mixed", "resolving", "escalating"}
    assert 0 <= first.confidence <= 1
    assert first.verification_state
    assert first.timeline
    assert first.source_mix.social + first.source_mix.media + first.source_mix.official >= 1


def test_cross_source_variants_collapse_into_single_topic(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="power-1",
                url="https://demo.local/power-1",
                source_type="social",
                source_name="Telegram / Западный",
                published_at=datetime.fromisoformat("2026-04-03T08:10:00+03:00"),
                title="На Западном пропал свет в нескольких домах",
                text="Жители Западного района Ростова пишут, что вечером на Малиновского пропало электричество.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
            RawEvent(
                event_id="power-2",
                url="https://demo.local/power-2",
                source_type="media",
                source_name="Городское медиа",
                published_at=datetime.fromisoformat("2026-04-03T08:45:00+03:00"),
                title="Перебои с электричеством зафиксированы на Малиновского",
                text="В Ростове-на-Дону сообщили о локальном отключении электроэнергии на улице Малиновского в утренние часы.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
            RawEvent(
                event_id="power-3",
                url="https://demo.local/power-3",
                source_type="official",
                source_name="Администрация района",
                published_at=datetime.fromisoformat("2026-04-03T09:05:00+03:00"),
                title="Энергетики устраняют локальное нарушение на Малиновского",
                text="Специалисты работают над восстановлением электроснабжения на улице Малиновского в Ростове-на-Дону.",
                municipality="Ростов-на-Дону",
                is_official=True,
            ),
        ]
    )

    topics = service.get_top_issues(limit=10).items
    matching = [item for item in topics if "малиновского" in item.topic.neutral_summary.lower() or "малиновского" in item.topic.label.lower()]
    assert matching
    assert matching[0].topic.event_count >= 2
    assert {"Городское медиа", "Администрация района"}.issubset(set(matching[0].topic.sources))


def test_unrelated_same_day_posts_do_not_merge_into_single_topic(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="unrelated-1",
                url="https://demo.local/unrelated-1",
                source_type="media",
                source_name="Новости города",
                published_at=datetime.fromisoformat("2026-04-03T10:00:00+03:00"),
                title="В Ростове задержали сбежавшего из колонии заключенного",
                text="В Ростовской области задержали заключенного, который ранее сбежал из колонии.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
            RawEvent(
                event_id="unrelated-2",
                url="https://demo.local/unrelated-2",
                source_type="official",
                source_name="Администрация города",
                published_at=datetime.fromisoformat("2026-04-03T10:20:00+03:00"),
                title="В Ростове стартовал форум молодых инженеров",
                text="В Ростове-на-Дону стартовал форум молодых инженеров и разработчиков на площадке ДГТУ.",
                municipality="Ростов-на-Дону",
                is_official=True,
            ),
            RawEvent(
                event_id="unrelated-3",
                url="https://demo.local/unrelated-3",
                source_type="social",
                source_name="VK / Городской паблик",
                published_at=datetime.fromisoformat("2026-04-03T10:40:00+03:00"),
                title="Жители жалуются на запах гари на Северном",
                text="Жители Северного района Ростова жалуются на сильный запах гари и дым во дворе.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
        ]
    )

    clusters = service.analytics._build_clusters(service.db.fetch_events())
    labels = {service.analytics._cluster_to_topic(cluster).label for cluster in clusters}

    assert any("задержали" in label.lower() for label in labels)
    assert any("запах гари" in label.lower() for label in labels)
    assert not any("форум" in label.lower() for label in labels)


def test_low_signal_social_posts_do_not_pollute_problem_clusters(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="incident-1",
                url="https://demo.local/incident-1",
                source_type="social",
                source_name="Telegram / Ростов Главный",
                published_at=datetime.fromisoformat("2026-04-04T21:00:00+03:00"),
                title="Тройное ДТП произошло на въезде в Ростов",
                text="На въезде в Ростов столкнулись сразу три автомобиля, на месте работают экстренные службы.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
            RawEvent(
                event_id="noise-1",
                url="https://demo.local/noise-1",
                source_type="social",
                source_name="Telegram / Это Ростов новости",
                published_at=datetime.fromisoformat("2026-04-04T21:05:00+03:00"),
                title="Жиза Это Ростов! Подпишись",
                text="Жиза. Это Ростов! Подпишись, прислать новость, подписывайтесь на наш канал в MAX.",
                municipality=None,
                is_official=False,
            ),
            RawEvent(
                event_id="noise-2",
                url="https://demo.local/noise-2",
                source_type="social",
                source_name="Telegram / Это Ростов новости",
                published_at=datetime.fromisoformat("2026-04-04T21:06:00+03:00"),
                title="Девушка испекла кулич с глазурью",
                text="Девушка испекла кулич с глазурью. Сладкоежки на месте? Это Ростов, подпишись и присылай новость.",
                municipality=None,
                is_official=False,
            ),
        ]
    )

    topics = service.get_top_issues(limit=10).items
    assert topics
    top_topic = topics[0].topic
    snippets = " ".join(item.snippet.lower() for item in top_topic.evidence)

    assert "дтп" in top_topic.label.lower() or "автомоб" in top_topic.neutral_summary.lower()
    assert "кулич" not in snippets
    assert "жиза" not in snippets


def test_unrelated_incidents_without_shared_anchors_stay_separate(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service.db.upsert_events(
        [
            RawEvent(
                event_id="attack-1",
                url="https://demo.local/attack-1",
                source_type="media",
                source_name="Новости Таганрога",
                published_at=datetime.fromisoformat("2026-04-04T20:10:00+03:00"),
                title="Один человек погиб и еще четверо пострадали после атаки по Таганрогу",
                text="После атаки по Таганрогу один человек погиб и еще четверо пострадали. На месте работают экстренные службы.",
                municipality="Таганрог",
                is_official=False,
            ),
            RawEvent(
                event_id="attack-2",
                url="https://demo.local/attack-2",
                source_type="official",
                source_name="Администрация Таганрога",
                published_at=datetime.fromisoformat("2026-04-04T20:20:00+03:00"),
                title="В Таганроге подтверждены последствия ночной атаки",
                text="В Таганроге подтверждены последствия ночной атаки, пострадавшим оказывается медицинская помощь.",
                municipality="Таганрог",
                is_official=True,
            ),
            RawEvent(
                event_id="crime-1",
                url="https://demo.local/crime-1",
                source_type="social",
                source_name="Telegram / Ростов Главный",
                published_at=datetime.fromisoformat("2026-04-04T20:25:00+03:00"),
                title="Мужчина напал на женщину после ДТП в центре Ростова",
                text="После аварии в центре Ростова мужчина напал на женщину, очевидцы вызвали полицию.",
                municipality="Ростов-на-Дону",
                is_official=False,
            ),
        ]
    )

    topics = service.get_top_issues(limit=10).items
    labels = [item.topic.label.lower() for item in topics]

    assert any("таганрог" in label for label in labels)
    assert any("женщин" in label or "дтп" in label for label in labels)
    assert sum(1 for label in labels if "таганрог" in label and ("женщин" in label or "дтп" in label)) == 0


def test_region_wide_alias_does_not_collapse_into_rostov_city(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    event = RawEvent(
        event_id="region-alert",
        url="https://demo.local/region-alert",
        source_type="media",
        source_name="Областные новости",
        published_at=datetime.fromisoformat("2026-04-04T09:00:00+03:00"),
        title="В Ростовской области объявлена беспилотная опасность",
        text="В Ростовской области ночью объявлена беспилотная опасность, жителям рекомендовали сохранять осторожность.",
        municipality=None,
        is_official=False,
    )

    enriched = service.analytics._enrich_event(event)

    assert enriched.municipality == "unknown"


def test_driver_incident_is_classified_as_transport(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    event = RawEvent(
        event_id="road-incident",
        url="https://demo.local/road-incident",
        source_type="social",
        source_name="Telegram / Ростов",
        published_at=datetime.fromisoformat("2026-04-04T12:00:00+03:00"),
        title="Водитель сбил ребенка во дворе Ростова",
        text="Во дворе на улице Пасаева водитель сбил ребенка, на месте ДТП работают врачи и полиция.",
        municipality="Ростов-на-Дону",
        is_official=False,
    )

    enriched = service.analytics._enrich_event(event)

    assert enriched.sector == "Дороги и транспорт"
