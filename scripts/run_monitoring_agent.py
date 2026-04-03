from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from madrigal_assistant.agent import MonitoringAgent
from madrigal_assistant.services import RegionalPulseService
from madrigal_assistant.settings import ROOT_DIR


def main() -> None:
    service = RegionalPulseService()
    top_issues = service.get_top_issues(limit=10)
    raw_events = service.get_raw_events()
    agent = MonitoringAgent(service.region_config["region_name"])
    briefing = agent.build_briefing(top_issues, raw_events.items)

    output_path = ROOT_DIR / "datasets" / "rostov" / "briefings" / "agent_preview.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
