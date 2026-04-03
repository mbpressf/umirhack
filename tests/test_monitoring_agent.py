from pathlib import Path

from madrigal_assistant.agent import MonitoringAgent
from madrigal_assistant.services import RegionalPulseService


def test_monitoring_agent_builds_briefing(tmp_path: Path) -> None:
    service = RegionalPulseService(db_path=tmp_path / "agent.db")
    service.import_seed()
    top = service.get_top_issues(limit=10)
    raw = service.get_raw_events()

    agent = MonitoringAgent(service.region_config["region_name"])
    briefing = agent.build_briefing(top, raw.items, [])

    assert briefing["region"] == "Ростовская область"
    assert briefing["urgent_topics"]
    assert "next_collection_targets" in briefing
    assert "executive_summary" in briefing
