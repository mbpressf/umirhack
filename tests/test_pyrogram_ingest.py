from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from madrigal_assistant.ingest.pyrogram_client import PyrogramCollector
from madrigal_assistant.models import SourceDefinition
from madrigal_assistant.settings import _build_live_sources


class _FakeAsyncIterator:
    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        value = self._items[self._index]
        self._index += 1
        return value


class _FakePyrogramClient:
    history_items = []
    comment_items = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get_chat_history(self, chat_id, limit):
        assert chat_id == "@RostovRegion"
        return _FakeAsyncIterator(self.history_items[:limit])

    def search_messages(self, chat_id, query, limit):
        assert chat_id == "@RostovRegion"
        assert query == "электричество"
        return _FakeAsyncIterator(self.history_items[:limit])

    async def get_messages(self, chat_id, message_id):
        assert chat_id == "@RostovRegion"
        for item in self.history_items:
            if item.id == message_id:
                return item
        return None

    def get_discussion_replies(self, chat_id, message_id, limit):
        assert chat_id == "@RostovRegion"
        assert message_id == 101
        return _FakeAsyncIterator(self.comment_items[:limit])


def _message(
    message_id: int,
    text: str,
    *,
    username: str = "RostovRegion",
    title: str = "Ростовская область",
    is_comment: bool = False,
):
    return SimpleNamespace(
        id=message_id,
        text=text,
        caption=None,
        poll=None,
        media=None,
        date=datetime.fromisoformat("2026-04-05T10:00:00+03:00"),
        views=1500,
        replies=SimpleNamespace(replies=4),
        link=f"https://t.me/{username}/{message_id}",
        chat=SimpleNamespace(id=-100123, username=username, title=title),
        from_user=None if not is_comment else SimpleNamespace(first_name="Иван", last_name="Петров", username="ivanpetrov"),
        sender_chat=None if is_comment else SimpleNamespace(title=title, username=username),
        reply_to_message_id=None if not is_comment else 101,
        photo=None,
        video=None,
        document=None,
        audio=None,
        voice=None,
        animation=None,
        sticker=None,
    )


def test_pyrogram_collector_fetches_history_and_comments(monkeypatch) -> None:
    root = _message(101, "В Батайске снова отключили электричество в нескольких кварталах.")
    comment = _message(202, "Жители пишут, что света нет уже второй час.", is_comment=True)
    _FakePyrogramClient.history_items = [root]
    _FakePyrogramClient.comment_items = [comment]

    monkeypatch.setattr("madrigal_assistant.ingest.pyrogram_client.Client", _FakePyrogramClient)
    monkeypatch.setenv("PYROGRAM_API_ID", "12345")
    monkeypatch.setenv("PYROGRAM_API_HASH", "hash")
    monkeypatch.setenv("PYROGRAM_SESSION_STRING", "session")

    collector = PyrogramCollector(region_name="Ростовская область")
    source = SourceDefinition(
        id="telegram_pyrogram_comments",
        name="Telegram / Правительство Ростовской области",
        kind="official",
        fetcher="telegram_pyrogram",
        url="https://t.me/RostovRegion",
        chat_id="@RostovRegion",
        include_comments=True,
        comment_limit=10,
        is_official=True,
    )

    events = collector.fetch_source(source, limit=5)

    assert len(events) == 2
    assert events[0].is_official is True
    assert events[0].source_type == "official"
    assert events[1].is_official is False
    assert events[1].source_type == "social"
    assert events[1].author == "Иван Петров (@ivanpetrov)"
    assert events[1].metadata["is_comment"] is True
    assert events[1].metadata["thread_root_message_id"] == 101


def test_pyrogram_collector_uses_search_query(monkeypatch) -> None:
    root = _message(101, "В Ростове обсуждают отключение электричества на Западном.")
    _FakePyrogramClient.history_items = [root]
    _FakePyrogramClient.comment_items = []

    monkeypatch.setattr("madrigal_assistant.ingest.pyrogram_client.Client", _FakePyrogramClient)
    monkeypatch.setenv("PYROGRAM_API_ID", "12345")
    monkeypatch.setenv("PYROGRAM_API_HASH", "hash")
    monkeypatch.setenv("PYROGRAM_SESSION_STRING", "session")

    collector = PyrogramCollector(region_name="Ростовская область")
    source = SourceDefinition(
        id="telegram_pyrogram_search",
        name="Telegram / РостовRegion Search",
        kind="social",
        fetcher="telegram_pyrogram",
        url="https://t.me/RostovRegion",
        chat_id="@RostovRegion",
        search_query="электричество",
    )

    events = collector.fetch_source(source, limit=3)

    assert len(events) == 1
    assert "электрич" in events[0].text.lower()
    assert events[0].metadata["search_query"] == "электричество"


def test_build_live_sources_respects_requires_all_env(monkeypatch) -> None:
    payload = {
        "sources": [
            {
                "id": "telegram_pyrogram_live",
                "enabled_in_live_config": True,
                "status": "stable",
                "requires_all_env": ["PYROGRAM_API_ID", "PYROGRAM_API_HASH"],
            }
        ]
    }

    monkeypatch.delenv("PYROGRAM_API_ID", raising=False)
    monkeypatch.delenv("PYROGRAM_API_HASH", raising=False)
    assert _build_live_sources(payload) == []

    monkeypatch.setenv("PYROGRAM_API_ID", "1")
    monkeypatch.setenv("PYROGRAM_API_HASH", "hash")
    assert len(_build_live_sources(payload)) == 1
