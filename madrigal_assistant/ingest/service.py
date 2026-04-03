from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from madrigal_assistant.models import IngestSourceStat, RawEvent, SourceDefinition
from madrigal_assistant.text import first_sentence, shorten, stable_event_id, strip_html

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Madrigal Regional Pulse)"}


def _fetch_text(url: str) -> str:
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "ignore")


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
            text = " ".join(text_node.stripped_strings)
            if not text:
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
