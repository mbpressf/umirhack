from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from madrigal_assistant.models import RawEvent


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(3):
            try:
                connection = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA journal_mode=WAL;")
                connection.execute("PRAGMA foreign_keys=ON;")
                connection.execute("PRAGMA busy_timeout=30000;")
                return connection
            except sqlite3.OperationalError as error:
                last_error = error
                if "unable to open database file" not in str(error).lower() or attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))
        raise last_error or sqlite3.OperationalError("unable to open database file")

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
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    provider TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
                    ON chat_sessions(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    provider TEXT,
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
                    ON chat_messages(session_id, created_at ASC);
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

    def _ensure_chat_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                provider TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
                ON chat_sessions(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider TEXT,
                citations_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
                ON chat_messages(session_id, created_at ASC);
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

    def get_user(self, user_id: int) -> dict | None:
        try:
            with self._connect() as connection:
                self._ensure_users_table(connection)
                row = connection.execute(
                    "SELECT id, login, created_at FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

    def create_chat_session(self, user_id: int, title: str, provider: str | None = None) -> dict | None:
        try:
            with self._connect() as connection:
                self._ensure_users_table(connection)
                self._ensure_chat_tables(connection)
                cursor = connection.execute(
                    """
                    INSERT INTO chat_sessions (user_id, title, provider)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, title, provider),
                )
                session_id = cursor.lastrowid
                row = connection.execute(
                    """
                    SELECT id, user_id, title, created_at, updated_at
                    FROM chat_sessions
                    WHERE id = ?
                    """,
                    (session_id,),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

    def list_chat_sessions(self, user_id: int) -> list[dict]:
        try:
            with self._connect() as connection:
                self._ensure_chat_tables(connection)
                rows = connection.execute(
                    """
                    SELECT
                        s.id,
                        s.user_id,
                        s.title,
                        s.created_at,
                        s.updated_at,
                        (
                            SELECT content
                            FROM chat_messages AS m
                            WHERE m.session_id = s.id
                            ORDER BY m.id DESC
                            LIMIT 1
                        ) AS last_message_preview
                    FROM chat_sessions AS s
                    WHERE s.user_id = ?
                    ORDER BY s.updated_at DESC, s.id DESC
                    """,
                    (user_id,),
                ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    def get_chat_session(self, session_id: int, user_id: int) -> dict | None:
        try:
            with self._connect() as connection:
                self._ensure_chat_tables(connection)
                row = connection.execute(
                    """
                    SELECT
                        s.id,
                        s.user_id,
                        s.title,
                        s.created_at,
                        s.updated_at,
                        (
                            SELECT content
                            FROM chat_messages AS m
                            WHERE m.session_id = s.id
                            ORDER BY m.id DESC
                            LIMIT 1
                        ) AS last_message_preview
                    FROM chat_sessions AS s
                    WHERE s.id = ? AND s.user_id = ?
                    """,
                    (session_id, user_id),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

    def update_chat_session_title(self, session_id: int, user_id: int, title: str) -> None:
        try:
            with self._connect() as connection:
                self._ensure_chat_tables(connection)
                connection.execute(
                    """
                    UPDATE chat_sessions
                    SET title = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                    """,
                    (title, session_id, user_id),
                )
        except sqlite3.Error:
            return None

    def create_chat_message(
        self,
        session_id: int,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        provider: str | None = None,
    ) -> dict | None:
        try:
            payload = json.dumps(citations or [], ensure_ascii=False)
            with self._connect() as connection:
                self._ensure_chat_tables(connection)
                cursor = connection.execute(
                    """
                    INSERT INTO chat_messages (session_id, role, content, provider, citations_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, role, content, provider, payload),
                )
                connection.execute(
                    """
                    UPDATE chat_sessions
                    SET updated_at = CURRENT_TIMESTAMP, provider = COALESCE(?, provider)
                    WHERE id = ?
                    """,
                    (provider, session_id),
                )
                message_id = cursor.lastrowid
                row = connection.execute(
                    """
                    SELECT id, session_id, role, content, provider, citations_json, created_at
                    FROM chat_messages
                    WHERE id = ?
                    """,
                    (message_id,),
                ).fetchone()
            if not row:
                return None
            record = dict(row)
            record["citations"] = json.loads(record.pop("citations_json") or "[]")
            return record
        except sqlite3.Error:
            return None

    def list_chat_messages(self, session_id: int, user_id: int) -> list[dict]:
        try:
            with self._connect() as connection:
                self._ensure_chat_tables(connection)
                session = connection.execute(
                    "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
                if not session:
                    return []
                rows = connection.execute(
                    """
                    SELECT id, session_id, role, content, provider, citations_json, created_at
                    FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (session_id,),
                ).fetchall()
            items: list[dict] = []
            for row in rows:
                record = dict(row)
                record["citations"] = json.loads(record.pop("citations_json") or "[]")
                items.append(record)
            return items
        except sqlite3.Error:
            return []
