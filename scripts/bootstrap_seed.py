from __future__ import annotations

from madrigal_assistant.services import RegionalPulseService


def main() -> None:
    service = RegionalPulseService()
    if service.db.fetch_events():
        print("Database already contains events, bootstrap skipped.")
        return
    result = service.import_seed()
    print(
        f"Bootstrap seed imported: imported={result.imported}, "
        f"updated={result.updated}, source={result.source}"
    )


if __name__ == "__main__":
    main()
