from __future__ import annotations

import json
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from madrigal_assistant.models import IngestSourceStat, RawEvent, SourceDefinition
from madrigal_assistant.text import clean_public_text, first_sentence, looks_like_promotional_noise, shorten, stable_event_id, strip_html

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Madrigal Regional Pulse)"}


def _fetch_text(url: str) -> str:
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "ignore")


def _fetch_json(url: str) -> dict:
    return json.loads(_fetch_text(url))


def _parse_datetime(raw_value: str | None, fallback: datetime | None = None) -> datetime:
    if not raw_value:
        return fallback or datetime.now().astimezone()
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        return fallback or datetime.now().astimezone()


def _extract_article_datetime(soup: BeautifulSoup, fallback: datetime) -> datetime:
    candidates = []
    for attr in ("article:published_time", "og:published_time", "pubdate"):
        node = soup.find("meta", attrs={"property": attr}) or soup.find("meta", attrs={"name": attr})
        if node and node.get("content"):
            candidates.append(node["content"])
    for node in soup.find_all(["time", "meta"]):
        if node.get("datetime"):
            candidates.append(node["datetime"])
        if node.get("content") and node.get("itemprop") in {"datePublished", "dateCreated"}:
            candidates.append(node["content"])
    for candidate in candidates:
        return _parse_datetime(candidate, fallback=fallback)
    return fallback


def _extract_article_text(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content") and len(meta["content"]) > 70:
        return " ".join(meta["content"].split())

    for selector in ("article", "main", ".content", ".article", ".news-text", ".entry-content"):
        node = soup.select_one(selector)
        if not node:
            continue
        paragraphs = [" ".join(item.stripped_strings) for item in node.find_all("p")]
        paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) > 40]
        if paragraphs:
            return " ".join(paragraphs[:4])

    paragraphs = [" ".join(item.stripped_strings) for item in soup.find_all("p")]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) > 40]
    return " ".join(paragraphs[:4]) if paragraphs else ""


def _extract_article_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector in ("meta[property='og:title']", "h1", "title"):
        node = soup.select_one(selector)
        if not node:
            continue
        if node.name == "meta" and node.get("content"):
            return " ".join(node["content"].split())
        text = " ".join(node.stripped_strings)
        if text:
            return text
    return fallback


class IngestionService:
    def __init__(self, region_config: dict):
        self.region_config = region_config
        self.sources = [SourceDefinition.model_validate(item) for item in region_config["sources"]]

    def run(self, max_per_source: int = 8) -> tuple[list[RawEvent], list[IngestSourceStat]]:
        collected: list[RawEvent] = []
        stats: list[IngestSourceStat] = []
        for source in self.sources:
            limit = min(source.max_items, max_per_source)
            try:
                if source.fetcher == "rss":
                    items = self._fetch_rss(source, limit)
                elif source.fetcher == "html":
                    items = self._fetch_html(source, limit)
                elif source.fetcher == "telegram":
                    items = self._fetch_telegram(source, limit)
                elif source.fetcher == "vk_api":
                    items = self._fetch_vk_api(source, limit)
                else:
                    raise ValueError(f"Unsupported fetcher: {source.fetcher}")
                collected.extend(items)
                stats.append(
                    IngestSourceStat(
                        source_id=source.id,
                        source_name=source.name,
                        scanned=len(items),
                        inserted=0,
                        updated=0,
                        status="ok",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                stats.append(
                    IngestSourceStat(
                        source_id=source.id,
                        source_name=source.name,
                        scanned=0,
                        inserted=0,
                        updated=0,
                        status="error",
                        error=str(exc),
                    )
                )
        return collected, stats

    def _fetch_rss(self, source: SourceDefinition, limit: int) -> list[RawEvent]:
        root = ElementTree.fromstring(_fetch_text(source.url))
        items = root.findall("./channel/item")[:limit]
        events: list[RawEvent] = []
        for item in items:
            link = (item.findtext("link") or "").strip()
            title = strip_html(item.findtext("title") or "")
            description = strip_html(item.findtext("description") or "")
            content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            text = strip_html(content) if content else description
            published_at = _parse_datetime(item.findtext("pubDate"))
            guid = (item.findtext("guid") or link or title).strip()
            events.append(
                RawEvent(
                    event_id=stable_event_id(source.id, guid),
                    external_id=guid,
                    url=link or source.url,
                    source_id=source.id,
                    source_type=source.kind,
                    source_name=source.name,
                    region=self.region_config["region_name"],
                    published_at=published_at,
                    title=title or first_sentence(text),
                    text=text or title,
                    is_official=source.is_official,
                )
            )
        return events

    def _fetch_html(self, source: SourceDefinition, limit: int) -> list[RawEvent]:
        page_html = _fetch_text(source.url)
        soup = BeautifulSoup(page_html, "html.parser")
        seen: set[str] = set()
        candidates: list[tuple[str, str]] = []
        for anchor in soup.find_all("a", href=True):
            href = urljoin(source.url, anchor["href"])
            title = " ".join(anchor.stripped_strings)
            if not title:
                continue
            if source.link_regex and not re.search(source.link_regex, href):
                continue
            if href in seen:
                continue
            seen.add(href)
            candidates.append((href, title))

        events: list[RawEvent] = []
        now = datetime.now().astimezone()
        for href, listing_title in candidates[:limit]:
            metadata = {}
            try:
                detail_soup = BeautifulSoup(_fetch_text(href), "html.parser")
                title = _extract_article_title(detail_soup, listing_title)
                published_at = _extract_article_datetime(detail_soup, now)
                text = _extract_article_text(detail_soup) or listing_title
            except Exception as exc:  # noqa: BLE001
                title = listing_title
                published_at = now
                text = listing_title
                metadata["detail_fetch_error"] = str(exc)
            events.append(
                RawEvent(
                    event_id=stable_event_id(source.id, href),
                    external_id=href,
                    url=href,
                    source_id=source.id,
                    source_type=source.kind,
                    source_name=source.name,
                    region=self.region_config["region_name"],
                    published_at=published_at,
                    title=title,
                    text=text,
                    is_official=source.is_official,
                    metadata=metadata,
                )
            )
        return events

    def _fetch_telegram(self, source: SourceDefinition, limit: int) -> list[RawEvent]:
        soup = BeautifulSoup(_fetch_text(source.url), "html.parser")
        events: list[RawEvent] = []
        for message in soup.select(".tgme_widget_message")[: limit * 3]:
            text_node = message.select_one(".tgme_widget_message_text")
            if not text_node:
                continue
            text = clean_public_text(" ".join(text_node.stripped_strings))
            if not text or looks_like_promotional_noise(text):
                continue
            post_id = message.get("data-post", "")
            date_node = message.select_one("time")
            published_at = _parse_datetime(date_node.get("datetime") if date_node else None)
            link_node = message.select_one(".tgme_widget_message_date")
            href = urljoin("https://t.me", link_node["href"]) if link_node and link_node.get("href") else source.url
            views_node = message.select_one(".tgme_widget_message_views")
            engagement = None
            if views_node:
                digits = re.sub(r"\D", "", views_node.get_text(" ", strip=True))
                engagement = int(digits) if digits else None
            title = shorten(first_sentence(text), 100)
            events.append(
                RawEvent(
                    event_id=stable_event_id(source.id, post_id or href),
                    external_id=post_id or href,
                    url=href,
                    source_id=source.id,
                    source_type=source.kind,
                    source_name=source.name,
                    region=self.region_config["region_name"],
                    published_at=published_at,
                    title=unescape(title),
                    text=unescape(text),
                    engagement=engagement,
                    is_official=source.is_official,
                )
            )
            if len(events) >= limit:
                break
        return events

    def _fetch_vk_api(self, source: SourceDefinition, limit: int) -> list[RawEvent]:
        token_name = source.requires_env or "VK_API_TOKEN"
        token = os.getenv(token_name)
        if not token:
            raise ValueError(f"{token_name} is not set")

        params: dict[str, str | int] = {
            "access_token": token,
            "v": "5.199",
            "count": min(limit, 100),
            "filter": source.vk_filter or "owner",
        }
        if source.owner_id is not None:
            params["owner_id"] = source.owner_id
        else:
            domain = source.domain or self._extract_vk_domain(source.url)
            if not domain:
                raise ValueError("VK source requires domain or owner_id")
            params["domain"] = domain

        payload = _fetch_json(f"https://api.vk.com/method/wall.get?{urlencode(params)}")
        if payload.get("error"):
            error = payload["error"]
            raise ValueError(f"VK API error {error.get('error_code')}: {error.get('error_msg')}")

        items = payload.get("response", {}).get("items", [])
        events: list[RawEvent] = []
        for item in items:
            text = clean_public_text(self._extract_vk_post_text(item))
            if not text:
                continue
            url = f"https://vk.com/wall{item.get('owner_id')}_{item.get('id')}"
            title = shorten(first_sentence(text), 100) or source.name
            if looks_like_promotional_noise(text, title=title):
                continue
            engagement = (item.get("views") or {}).get("count")
            if engagement is None:
                engagement = sum((item.get(metric) or {}).get("count", 0) for metric in ("likes", "comments", "reposts"))

            events.append(
                RawEvent(
                    event_id=stable_event_id(source.id, str(item.get("id") or url)),
                    external_id=str(item.get("id") or url),
                    url=url,
                    source_id=source.id,
                    source_type=source.kind,
                    source_name=source.name,
                    region=self.region_config["region_name"],
                    published_at=datetime.fromtimestamp(item.get("date", datetime.now().timestamp())).astimezone(),
                    title=title,
                    text=text,
                    engagement=engagement,
                    is_official=source.is_official,
                    metadata={
                        "likes": (item.get("likes") or {}).get("count"),
                        "comments": (item.get("comments") or {}).get("count"),
                        "reposts": (item.get("reposts") or {}).get("count"),
                        "attachments": [attachment.get("type") for attachment in item.get("attachments", [])],
                    },
                )
            )
            if len(events) >= limit:
                break
        return events

    @staticmethod
    def _extract_vk_domain(url: str) -> str | None:
        match = re.search(r"vk\.com/([^/?#]+)", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_vk_post_text(item: dict) -> str:
        text_parts = []
        if item.get("text"):
            text_parts.append(item["text"])
        for history_item in item.get("copy_history", []):
            if history_item.get("text"):
                text_parts.append(history_item["text"])
        attachments = item.get("attachments", [])
        for attachment in attachments:
            attachment_type = attachment.get("type")
            payload = attachment.get(attachment_type, {})
            if attachment_type == "article":
                text_parts.extend([payload.get("title", ""), payload.get("description", "")])
            elif attachment_type in {"video", "audio", "podcast"}:
                text_parts.extend([payload.get("title", ""), payload.get("description", "")])
            elif attachment_type == "link":
                text_parts.extend([payload.get("title", ""), payload.get("caption", ""), payload.get("description", "")])
            elif attachment_type == "photo":
                text_parts.append(payload.get("text", ""))
        return " ".join(part.strip() for part in text_parts if part and str(part).strip())
