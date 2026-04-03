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
    assert len(payload["items"]) == 10
