from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from madrigal_assistant.agent import MonitoringAgent
from madrigal_assistant.services import RegionalPulseService
from madrigal_assistant.settings import ROOT_DIR


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_catalog_csv(catalog_json_path: Path, csv_path: Path) -> None:
    payload = json.loads(catalog_json_path.read_text(encoding="utf-8"))
    rows = payload.get("sources", payload)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "name",
                "kind",
                "fetcher",
                "url",
                "status",
                "enabled_in_live_config",
                "priority",
                "coverage",
                "requires_env",
                "domain",
                "owner_id",
                "tags",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            prepared = {key: row.get(key) for key in writer.fieldnames}
            prepared["tags"] = ", ".join(row.get("tags", []))
            writer.writerow(prepared)


def discover_manual_inputs(manual_dir: Path, explicit_inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    if manual_dir.exists():
        for candidate in sorted(manual_dir.iterdir()):
            if candidate.is_file() and candidate.suffix.lower() in {".json", ".jsonl", ".csv"}:
                files.append(candidate)
    for raw_path in explicit_inputs:
        candidate = Path(raw_path)
        if candidate.exists() and candidate.is_file():
            files.append(candidate)

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for item in files:
        resolved = item.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)
    return unique_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Rostov datasets and build briefing artifacts.")
    parser.add_argument("--config", default=str(ROOT_DIR / "config" / "demo_region.rostov.json"))
    parser.add_argument("--catalog", default=str(ROOT_DIR / "config" / "source_catalog.rostov.json"))
    parser.add_argument("--db", default=str(ROOT_DIR / "datasets" / "rostov" / "collector.db"))
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "datasets" / "rostov"))
    parser.add_argument("--manual-dir", default=str(ROOT_DIR / "datasets" / "rostov" / "manual"))
    parser.add_argument("--manual-input", action="append", default=[])
    parser.add_argument("--max-per-source", type=int, default=8)
    parser.add_argument("--include-seed", action="store_true", default=True)
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--skip-manual", action="store_true")
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    briefing_dir = output_dir / "briefings"
    catalog_dir = output_dir / "catalog"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    service = RegionalPulseService(db_path=Path(args.db), config_path=Path(args.config))
    if args.reset_db:
        service.db.reset()
    if args.include_seed and not args.skip_seed:
        service.import_seed()

    manual_results = []
    if not args.skip_manual:
        for manual_path in discover_manual_inputs(Path(args.manual_dir), args.manual_input):
            result = service.import_manual(upload_bytes=manual_path.read_bytes(), filename=manual_path.name)
            manual_results.append({"path": str(manual_path), **result.model_dump()})

    ingest_result = service.run_ingest(max_per_source=args.max_per_source)
    raw_events = service.get_raw_events()
    top_issues = service.get_top_issues(limit=10)
    agent = MonitoringAgent(service.region_config["region_name"], source_catalog_path=Path(args.catalog))
    briefing = agent.build_briefing(top_issues, raw_events.items, ingest_result.source_stats)
    briefing_md = agent.to_markdown(briefing)

    raw_rows = [item.model_dump(mode="json") for item in raw_events.items]
    top_payload = top_issues.model_dump(mode="json")
    ingest_payload = ingest_result.model_dump(mode="json")

    raw_timestamped = raw_dir / f"raw_events_{timestamp}.jsonl"
    raw_latest = raw_dir / "latest_raw_events.jsonl"
    top_timestamped = raw_dir / f"top_issues_{timestamp}.json"
    top_latest = raw_dir / "latest_top_issues.json"
    stats_timestamped = raw_dir / f"source_stats_{timestamp}.json"
    stats_latest = raw_dir / "latest_source_stats.json"
    manual_timestamped = raw_dir / f"manual_imports_{timestamp}.json"
    manual_latest = raw_dir / "latest_manual_imports.json"
    briefing_timestamped_json = briefing_dir / f"briefing_{timestamp}.json"
    briefing_latest_json = briefing_dir / "latest_briefing.json"
    briefing_timestamped_md = briefing_dir / f"briefing_{timestamp}.md"
    briefing_latest_md = briefing_dir / "latest_briefing.md"

    write_jsonl(raw_timestamped, raw_rows)
    write_jsonl(raw_latest, raw_rows)
    write_json(top_timestamped, top_payload)
    write_json(top_latest, top_payload)
    write_json(stats_timestamped, ingest_payload)
    write_json(stats_latest, ingest_payload)
    write_json(manual_timestamped, manual_results)
    write_json(manual_latest, manual_results)
    write_json(briefing_timestamped_json, briefing)
    write_json(briefing_latest_json, briefing)
    briefing_timestamped_md.write_text(briefing_md, encoding="utf-8")
    briefing_latest_md.write_text(briefing_md, encoding="utf-8")

    catalog_json_copy = catalog_dir / "source_catalog.json"
    catalog_csv_copy = catalog_dir / "source_catalog.csv"
    catalog_json_copy.write_text(Path(args.catalog).read_text(encoding="utf-8"), encoding="utf-8")
    export_catalog_csv(Path(args.catalog), catalog_csv_copy)

    print(json.dumps(
        {
            "raw_events": len(raw_rows),
            "top_issues": len(top_issues.items),
            "inserted": ingest_result.inserted,
            "updated": ingest_result.updated,
            "manual_files": len(manual_results),
            "manual_imported": sum(item["imported"] for item in manual_results),
            "output_dir": str(output_dir),
            "briefing_md": str(briefing_latest_md),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
