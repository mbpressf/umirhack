from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from madrigal_assistant.text import clean_public_text


class SourceDefinition(BaseModel):
    id: str
    name: str
    kind: str
    fetcher: str
    url: str
    max_items: int = 10
    is_official: bool = False
    link_regex: str | None = None
    channel: str | None = None
    domain: str | None = None
    owner_id: int | None = None
    vk_filter: str | None = None
    requires_env: str | None = None
    status: str | None = None
    enabled_in_live_config: bool | None = None
    priority: int | None = None
    coverage: str | None = None
    tags: list[str] = Field(default_factory=list)


class RawEvent(BaseModel):
    event_id: str | None = None
    external_id: str | None = None
    url: str
    source_id: str | None = None
    source_type: str
    source_name: str
    region: str = "Ростовская область"
    published_at: datetime
    title: str | None = None
    text: str
    author: str | None = None
    municipality: str | None = None
    engagement: int | None = None
    is_official: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def normalize_source_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_public_text(value)
        return cleaned or None

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: str | None) -> str:
        return clean_public_text(value)


class TopicEvidence(BaseModel):
    event_id: str
    source_name: str
    source_type: str
    url: str
    published_at: datetime
    snippet: str
    is_official: bool
    engagement: int | None = None


class ScoreBreakdown(BaseModel):
    surge: float
    diversity: float
    geography: float
    severity: float
    official_signal: float
    citizen_volume: float
    bot_penalty: float


class SourceMix(BaseModel):
    official: int = 0
    media: int = 0
    social: int = 0
    other: int = 0


class TopicSummary(BaseModel):
    topic_id: str
    label: str
    sector: str
    issue_relevance: float = 0.0
    confidence: float = 0.0
    trend: str = "stable"
    verification_state: str = "single_source"
    municipalities: list[str]
    first_seen: datetime
    last_seen: datetime
    event_count: int
    source_count: int
    neutral_summary: str
    evidence: list[TopicEvidence]
    contradiction_flag: bool
    bot_score: float
    score: float | None = None
    score_breakdown: ScoreBreakdown | None = None
    why_in_top: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_mix: SourceMix = Field(default_factory=SourceMix)


class TopIssue(BaseModel):
    rank: int
    topic: TopicSummary


class TopIssuesResponse(BaseModel):
    generated_at: datetime
    region: str
    total_topics: int
    items: list[TopIssue]


class ProblemTimelineEvent(BaseModel):
    published_at: datetime
    source_name: str
    source_type: str
    signal_kind: str
    snippet: str
    url: str


class ProblemCard(BaseModel):
    topic_id: str
    rank: int
    title: str
    sector: str
    municipalities: list[str]
    primary_municipality: str
    score: float | None = None
    confidence: float = 0.0
    trend: str
    verification_state: str
    urgency: str
    status: str
    summary: str
    why_now: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    latest_official_update: str | None = None
    latest_citizen_signal: str | None = None
    contradiction_flag: bool
    bot_score: float
    source_mix: SourceMix = Field(default_factory=SourceMix)
    evidence: list[TopicEvidence]
    timeline: list[ProblemTimelineEvent] = Field(default_factory=list)
    first_seen: datetime
    last_seen: datetime


class ProblemCardsResponse(BaseModel):
    generated_at: datetime
    region: str
    total_cards: int
    items: list[ProblemCard]


class SimilarTopic(BaseModel):
    topic_id: str
    label: str
    sector: str
    municipalities: list[str]
    similarity: float
    score: float | None = None
    confidence: float = 0.0
    verification_state: str = "single_source"
    reasons: list[str] = Field(default_factory=list)


class SimilarTopicsResponse(BaseModel):
    generated_at: datetime
    region: str
    topic_id: str | None = None
    query: str | None = None
    embedding_layer: dict[str, Any] = Field(default_factory=dict)
    items: list[SimilarTopic]


class TrendPoint(BaseModel):
    bucket_start: datetime
    value: int


class TrendSeries(BaseModel):
    topic_id: str
    label: str
    sector: str
    points: list[TrendPoint]


class TrendsResponse(BaseModel):
    generated_at: datetime
    region: str
    series: list[TrendSeries]


class IngestSourceStat(BaseModel):
    source_id: str
    source_name: str
    scanned: int
    inserted: int
    updated: int
    status: str
    error: str | None = None


class IngestRunResult(BaseModel):
    inserted: int
    updated: int
    scanned: int
    source_stats: list[IngestSourceStat]


class ImportSeedResponse(BaseModel):
    imported: int
    updated: int
    source: str


class IngestRequest(BaseModel):
    max_per_source: int = 8


class RawEventsResponse(BaseModel):
    generated_at: datetime
    region: str
    total_events: int
    items: list[RawEvent]


class AuthUser(BaseModel):
    id: int
    login: str
    created_at: str


class RegisterRequest(BaseModel):
    login: str
    password: str
    password_confirm: str


class LoginRequest(BaseModel):
    login: str
    password: str


class AuthResponse(BaseModel):
    user: AuthUser
