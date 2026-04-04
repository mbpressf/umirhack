from __future__ import annotations

import math
import os
from dataclasses import dataclass
from threading import Lock

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None

# По ТЗ используем локальную российскую open-source модель, а не зарубежный embedder.
DEFAULT_EMBEDDING_MODEL = "ai-forever/ru-en-RoSBERTa"


@dataclass
class EmbeddingLayerStatus:
    enabled: bool
    available: bool
    active: bool
    backend: str
    model_name: str
    device: str
    cache_size: int
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "active": self.active,
            "backend": self.backend,
            "model_name": self.model_name,
            "device": self.device,
            "cache_size": self.cache_size,
            "error": self.error,
        }


class EmbeddingService:
    def __init__(
        self,
        enabled: bool | None = None,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.enabled = _coerce_bool(os.getenv("MADRIGAL_ENABLE_EMBEDDINGS"), default=True) if enabled is None else enabled
        self.model_name = model_name or os.getenv("MADRIGAL_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.device = device or os.getenv("MADRIGAL_EMBEDDING_DEVICE", "cpu")
        self.batch_size = batch_size or int(os.getenv("MADRIGAL_EMBEDDING_BATCH_SIZE", "16"))
        self._model = None
        self._error: str | None = None
        self._cache: dict[str, tuple[float, ...]] = {}
        self._lock = Lock()

    def encode_texts(self, texts: list[str]) -> list[tuple[float, ...] | None]:
        normalized_inputs = [self._prepare_text(item) for item in texts]
        if not self.enabled:
            return [None for _ in normalized_inputs]
        if SentenceTransformer is None:
            self._error = "sentence-transformers is not installed"
            return [None for _ in normalized_inputs]

        missing = [item for item in dict.fromkeys(normalized_inputs) if item and item not in self._cache]
        if missing:
            model = self._ensure_model()
            if model is None:
                return [None for _ in normalized_inputs]
            try:
                vectors = model.encode(
                    missing,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
            except TypeError:  # pragma: no cover - compatibility shim
                vectors = model.encode(missing, batch_size=self.batch_size, show_progress_bar=False)
            for text, vector in zip(missing, vectors):
                self._cache[text] = self._normalize_vector(vector)
        return [self._cache.get(item) if item else None for item in normalized_inputs]

    def cosine_similarity(
        self,
        left: tuple[float, ...] | None,
        right: tuple[float, ...] | None,
    ) -> float:
        if not left or not right:
            return 0.0
        if len(left) != len(right):
            return 0.0
        return round(sum(a * b for a, b in zip(left, right)), 6)

    def mean_embedding(self, vectors: list[tuple[float, ...] | None]) -> tuple[float, ...] | None:
        usable = [vector for vector in vectors if vector]
        if not usable:
            return None
        size = len(usable[0])
        averaged = [0.0] * size
        for vector in usable:
            for index, value in enumerate(vector):
                averaged[index] += value
        count = float(len(usable))
        return self._normalize_vector(value / count for value in averaged)

    def status(self) -> EmbeddingLayerStatus:
        return EmbeddingLayerStatus(
            enabled=self.enabled,
            available=SentenceTransformer is not None,
            active=self._model is not None,
            backend="sentence-transformers",
            model_name=self.model_name,
            device=self.device,
            cache_size=len(self._cache),
            error=self._error,
        )

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        if SentenceTransformer is None:
            return None
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self._error = None
            except Exception as exc:  # pragma: no cover - depends on local runtime
                self._error = str(exc)
                self._model = None
        return self._model

    @staticmethod
    def _prepare_text(value: str | None) -> str:
        if not value:
            return ""
        return " ".join(value.strip().split())[:1200]

    @staticmethod
    def _normalize_vector(vector) -> tuple[float, ...]:
        values = [float(item) for item in vector]
        norm = math.sqrt(sum(item * item for item in values)) or 1.0
        return tuple(item / norm for item in values)


def _coerce_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}
