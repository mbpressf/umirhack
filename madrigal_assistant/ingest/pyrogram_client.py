from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from pyrogram import Client
except ImportError:  # pragma: no cover - optional dependency
    Client = None

from madrigal_assistant.models import RawEvent, SourceDefinition
from madrigal_assistant.text import clean_public_text, first_sentence, looks_like_promotional_noise, shorten, stable_event_id


class PyrogramCollector:
    def __init__(self, region_name: str) -> None:
        self.region_name = region_name

    def status(self) -> dict[str, object]:
        workdir = self._workdir()
        session_name = self._session_name()
        session_path = workdir / f"{session_name}.session"
        return {
            "installed": Client is not None,
            "api_id_configured": bool(os.getenv("PYROGRAM_API_ID")),
            "api_hash_configured": bool(os.getenv("PYROGRAM_API_HASH")),
            "session_string_configured": bool(os.getenv("PYROGRAM_SESSION_STRING")),
            "bot_token_configured": bool(os.getenv("PYROGRAM_BOT_TOKEN")),
            "session_file_present": session_path.exists(),
            "session_name": session_name,
            "workdir": str(workdir),
        }

    def fetch_source(self, source: SourceDefinition, limit: int) -> list[RawEvent]:
        if Client is None:
            raise ValueError("Pyrogram is not installed. Install pyrogram and tgcrypto to use telegram_pyrogram sources.")
        return self._run(self._fetch_source_async(source, limit))

    async def _fetch_source_async(self, source: SourceDefinition, limit: int) -> list[RawEvent]:
        app = self._build_client()
        async with app:
            root_messages = await self._load_root_messages(app, source, limit)
            events: list[RawEvent] = []
            seen_ids: set[str] = set()
            for message in root_messages:
                event = self._message_to_event(source, message, is_comment=False)
                if event and event.event_id not in seen_ids:
                    seen_ids.add(event.event_id)
                    events.append(event)
                if not source.include_comments:
                    continue
                for reply in await self._load_comments(app, source, message, limit):
                    comment_event = self._message_to_event(source, reply, is_comment=True, root_message=message)
                    if comment_event and comment_event.event_id not in seen_ids:
                        seen_ids.add(comment_event.event_id)
                        events.append(comment_event)
            return events

    def _build_client(self):
        api_id = os.getenv("PYROGRAM_API_ID")
        api_hash = os.getenv("PYROGRAM_API_HASH")
        if not api_id or not api_hash:
            raise ValueError("Set PYROGRAM_API_ID and PYROGRAM_API_HASH before using telegram_pyrogram sources.")

        session_name = self._session_name()
        workdir = self._workdir()
        workdir.mkdir(parents=True, exist_ok=True)
        session_string = os.getenv("PYROGRAM_SESSION_STRING")
        bot_token = os.getenv("PYROGRAM_BOT_TOKEN")

        session_path = workdir / f"{session_name}.session"
        if not session_string and not bot_token and not session_path.exists():
            raise ValueError(
                "No Pyrogram session found. Set PYROGRAM_SESSION_STRING, set PYROGRAM_BOT_TOKEN, "
                f"or create {session_path} with scripts/prepare_pyrogram_session.py."
            )

        kwargs: dict[str, Any] = {
            "name": session_name,
            "api_id": int(api_id),
            "api_hash": api_hash,
            "workdir": str(workdir),
            "no_updates": True,
            "sleep_threshold": 15,
        }
        if session_string:
            kwargs["session_string"] = session_string
        elif bot_token:
            kwargs["bot_token"] = bot_token
        return Client(**kwargs)

    async def _load_root_messages(self, app, source: SourceDefinition, limit: int) -> list[Any]:
        chat_id = self._resolve_chat_id(source)
        if source.message_id:
            message = await app.get_messages(chat_id, source.message_id)
            return [message] if message else []

        items: list[Any] = []
        if source.search_query:
            async for message in app.search_messages(chat_id, query=source.search_query, limit=limit):
                items.append(message)
                if len(items) >= limit:
                    break
            return items

        async for message in app.get_chat_history(chat_id, limit=limit):
            items.append(message)
            if len(items) >= limit:
                break
        return items

    async def _load_comments(self, app, source: SourceDefinition, root_message: Any, limit: int) -> list[Any]:
        chat_id = self._resolve_chat_id(source)
        comment_limit = source.comment_limit or min(max(limit, 1), 25)
        replies: list[Any] = []
        try:
            async for reply in app.get_discussion_replies(chat_id, root_message.id, limit=comment_limit):
                replies.append(reply)
                if len(replies) >= comment_limit:
                    break
        except Exception:  # noqa: BLE001
            return []
        return replies

    def _message_to_event(
        self,
        source: SourceDefinition,
        message: Any,
        *,
        is_comment: bool,
        root_message: Any | None = None,
    ) -> RawEvent | None:
        if message is None:
            return None

        text = clean_public_text(self._extract_text(message))
        if not text:
            return None

        title = shorten(first_sentence(text), 100) or source.name
        if looks_like_promotional_noise(text, title=title):
            return None

        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None) or source.chat_id or source.channel or source.url
        external_id = f"{chat_id}:{getattr(message, 'id', 'unknown')}"
        metadata = {
            "origin_fetcher": "telegram_pyrogram",
            "chat_id": getattr(chat, "id", None),
            "chat_title": getattr(chat, "title", None),
            "chat_username": getattr(chat, "username", None),
            "message_id": getattr(message, "id", None),
            "is_comment": is_comment,
            "search_query": source.search_query,
            "views": getattr(message, "views", None),
            "reply_to_message_id": getattr(getattr(message, "reply_to_message_id", None), "id", None)
            if hasattr(getattr(message, "reply_to_message_id", None), "id")
            else getattr(message, "reply_to_message_id", None),
        }
        if root_message is not None:
            metadata["thread_root_message_id"] = getattr(root_message, "id", None)
            metadata["thread_root_url"] = self._message_url(root_message, source.url)

        reply_meta = getattr(message, "replies", None)
        if reply_meta is not None:
            metadata["reply_count"] = getattr(reply_meta, "replies", None)

        author = self._extract_author(message)
        media_type = self._extract_media_type(message)
        if media_type:
            metadata["media_type"] = media_type

        published_at = getattr(message, "date", None) or datetime.now().astimezone()
        url = self._message_url(message, source.url)
        engagement = self._extract_engagement(message)
        source_type = source.kind if not is_comment or source.kind != "official" else "social"

        return RawEvent(
            event_id=stable_event_id(source.id, external_id),
            external_id=external_id,
            url=url,
            source_id=source.id,
            source_type=source_type,
            source_name=source.name,
            region=self.region_name,
            published_at=published_at,
            title=title,
            text=text,
            author=author,
            engagement=engagement,
            is_official=source.is_official and not is_comment,
            metadata=metadata,
        )

    def _resolve_chat_id(self, source: SourceDefinition) -> str | int:
        if source.chat_id is not None:
            return source.chat_id
        if source.channel:
            return source.channel if source.channel.startswith("@") else f"@{source.channel}"
        match = re.search(r"(?:t\.me|telegram\.me)/(?:s/)?([^/?#]+)", source.url)
        if match:
            username = match.group(1)
            return username if username.startswith("@") else f"@{username}"
        return source.url

    @staticmethod
    def _extract_text(message: Any) -> str:
        parts: list[str] = []
        for field_name in ("text", "caption"):
            value = getattr(message, field_name, None)
            if value:
                parts.append(str(value))

        poll = getattr(message, "poll", None)
        if poll and getattr(poll, "question", None):
            parts.append(str(poll.question))

        media = getattr(message, "media", None)
        if media and not parts:
            parts.append(str(media))

        return " ".join(part.strip() for part in parts if part and str(part).strip())

    @staticmethod
    def _extract_author(message: Any) -> str | None:
        from_user = getattr(message, "from_user", None)
        if from_user:
            display_name = " ".join(
                part for part in (getattr(from_user, "first_name", None), getattr(from_user, "last_name", None)) if part
            ).strip()
            username = getattr(from_user, "username", None)
            if username and display_name:
                return f"{display_name} (@{username})"
            if username:
                return f"@{username}"
            return display_name or None

        sender_chat = getattr(message, "sender_chat", None)
        if sender_chat:
            username = getattr(sender_chat, "username", None)
            title = getattr(sender_chat, "title", None)
            if username and title:
                return f"{title} (@{username})"
            return title or (f"@{username}" if username else None)
        return None

    @staticmethod
    def _extract_engagement(message: Any) -> int | None:
        views = getattr(message, "views", None)
        replies = getattr(getattr(message, "replies", None), "replies", None)
        if isinstance(views, int) and isinstance(replies, int):
            return views + replies
        if isinstance(views, int):
            return views
        if isinstance(replies, int):
            return replies
        return None

    @staticmethod
    def _extract_media_type(message: Any) -> str | None:
        media = getattr(message, "media", None)
        if media is not None:
            return str(media).lower()
        for attr in ("photo", "video", "document", "audio", "voice", "animation", "sticker"):
            if getattr(message, attr, None) is not None:
                return attr
        return None

    @staticmethod
    def _message_url(message: Any, fallback: str) -> str:
        link = getattr(message, "link", None)
        if link:
            return str(link)

        chat = getattr(message, "chat", None)
        username = getattr(chat, "username", None)
        message_id = getattr(message, "id", None)
        if username and message_id:
            username = username.lstrip("@")
            return f"https://t.me/{username}/{message_id}"
        return fallback

    @staticmethod
    def _run(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("PyrogramCollector.fetch_source() must be called from a synchronous context without an active event loop.")

    @staticmethod
    def _session_name() -> str:
        return os.getenv("PYROGRAM_SESSION_NAME", "madrigal_pyrogram")

    @staticmethod
    def _workdir() -> Path:
        return Path(os.getenv("PYROGRAM_WORKDIR", str(Path.cwd() / ".pyrogram")))
