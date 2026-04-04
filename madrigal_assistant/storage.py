from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from madrigal_assistant.models import RawEvent


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA foreign_keys=ON;")
        return connection

    def init(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS raw_events (
                    event_id TEXT PRIMARY KEY,
                    external_id TEXT,
                    url TEXT NOT NULL,
                    source_id TEXT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    region TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    title TEXT,
                    text TEXT NOT NULL,
                    author TEXT,
                    municipality TEXT,
                    engagement INTEGER,
                    is_official INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_events_source_url
                    ON raw_events(source_name, url);
                CREATE INDEX IF NOT EXISTS idx_raw_events_published_at
                    ON raw_events(published_at);
                CREATE INDEX IF NOT EXISTS idx_raw_events_source_type
                    ON raw_events(source_type);
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _ensure_users_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def reset(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM raw_events")

    def upsert_events(self, events: Iterable[RawEvent]) -> tuple[int, int]:
        items = list(events)
        if not items:
            return (0, 0)

        event_ids = [event.event_id for event in items if event.event_id]
        existing_ids: set[str] = set()
        if event_ids:
            placeholders = ",".join("?" for _ in event_ids)
            with self._connect() as connection:
                existing_ids = {
                    row["event_id"]
                    for row in connection.execute(
                        f"SELECT event_id FROM raw_events WHERE event_id IN ({placeholders})",
                        event_ids,
                    ).fetchall()
                }

        inserted = 0
        updated = 0
        with self._connect() as connection:
            for event in items:
                if event.event_id in existing_ids:
                    updated += 1
                else:
                    inserted += 1
                connection.execute(
                    """
                    INSERT INTO raw_events (
                        event_id, external_id, url, source_id, source_type, source_name, region,
                        published_at, title, text, author, municipality, engagement, is_official,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        external_id = excluded.external_id,
                        url = excluded.url,
                        source_id = excluded.source_id,
                        source_type = excluded.source_type,
                        source_name = excluded.source_name,
                        region = excluded.region,
                        published_at = excluded.published_at,
                        title = excluded.title,
                        text = excluded.text,
                        author = excluded.author,
                        municipality = excluded.municipality,
                        engagement = excluded.engagement,
                        is_official = excluded.is_official,
                        metadata_json = excluded.metadata_json,
                        imported_at = CURRENT_TIMESTAMP
                    """,
                    (
                        event.event_id,
                        event.external_id,
                        event.url,
                        event.source_id,
                        event.source_type,
                        event.source_name,
                        event.region,
                        event.published_at.isoformat(),
                        event.title,
                        event.text,
                        event.author,
                        event.municipality,
                        event.engagement,
                        1 if event.is_official else 0,
                        json.dumps(event.metadata, ensure_ascii=False),
                    ),
                )
        return (inserted, updated)

    def fetch_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        source_type: str | None = None,
    ) -> list[RawEvent]:
        clauses = []
        params: list[str] = []
        if start:
            clauses.append("published_at >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("published_at <= ?")
            params.append(end.isoformat())
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type.lower())

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM raw_events {where_clause} ORDER BY published_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            RawEvent(
                event_id=row["event_id"],
                external_id=row["external_id"],
                url=row["url"],
                source_id=row["source_id"],
                source_type=row["source_type"],
                source_name=row["source_name"],
                region=row["region"],
                published_at=row["published_at"],
                title=row["title"],
                text=row["text"],
                author=row["author"],
                municipality=row["municipality"],
                engagement=row["engagement"],
                is_official=bool(row["is_official"]),
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in rows
        ]

    def create_user(self, login: str, password_hash: str) -> dict | None:
        try:
            with self._connect() as connection:
                self._ensure_users_table(connection)
                cursor = connection.execute(
                    """
                    INSERT INTO users (login, password_hash)
                    VALUES (?, ?)
                    """,
                    (login, password_hash),
                )
                user_id = cursor.lastrowid
                row = connection.execute(
                    "SELECT id, login, created_at FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.IntegrityError:
            return None
        except sqlite3.Error:
            return None

    def get_user_with_secret(self, login: str) -> dict | None:
        try:
            with self._connect() as connection:
                self._ensure_users_table(connection)
                row = connection.execute(
                    "SELECT id, login, password_hash, created_at FROM users WHERE login = ?",
                    (login,),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None
