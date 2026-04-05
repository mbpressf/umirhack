from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid
from typing import Any

import httpx

from madrigal_assistant.settings import (
    get_chat_provider,
    get_gigachat_allow_insecure_ssl,
    get_gigachat_auth_key,
    get_gigachat_base_url,
    get_gigachat_ca_bundle,
    get_gigachat_model,
    get_gigachat_oauth_url,
    get_gigachat_scope,
    get_gigachat_timeout_seconds,
)
from madrigal_assistant.text import shorten


SYSTEM_PROMPT = """
Ты — аналитический помощник платформы «Сигнал».
Отвечай только на основе контекста, который передан из системы мониторинга.
Не выдумывай факты и не ссылайся на источники, которых нет в контексте.
Если данных недостаточно, прямо так и скажи.
Пиши кратко, по делу и в аналитическом стиле.
Если есть несколько сюжетов, сгруппируй их по важности.
""".strip()


class RegionalChatProvider:
    def __init__(self) -> None:
        self.provider = get_chat_provider()
        self.gigachat_auth_key = get_gigachat_auth_key()
        self.gigachat_model = get_gigachat_model()
        self.gigachat_scope = get_gigachat_scope()
        self.gigachat_base_url = get_gigachat_base_url()
        self.gigachat_oauth_url = get_gigachat_oauth_url()
        self.timeout_seconds = get_gigachat_timeout_seconds()
        self.ca_bundle = get_gigachat_ca_bundle()
        self.allow_insecure_ssl = get_gigachat_allow_insecure_ssl()
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    def status(self) -> dict[str, Any]:
        configured = self.provider == "gigachat" and bool(self.gigachat_auth_key)
        available = True
        mode = "llm" if configured else "fallback"
        return {
            "provider": self.provider if configured else "local",
            "mode": mode,
            "configured": configured,
            "available": available,
            "model": self.gigachat_model if configured else "extractive-rag",
            "retrieval_enabled": True,
            "details": {
                "gigachat_auth_configured": bool(self.gigachat_auth_key),
                "gigachat_scope": self.gigachat_scope,
                "gigachat_base_url": self.gigachat_base_url if configured else None,
                "ca_bundle_configured": bool(self.ca_bundle),
                "allow_insecure_ssl": self.allow_insecure_ssl,
            },
        }

    def answer(
        self,
        *,
        question: str,
        history: list[dict[str, str]],
        contexts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.provider == "gigachat" and self.gigachat_auth_key:
            try:
                content = self._answer_with_gigachat(question=question, history=history, contexts=contexts)
                return {
                    "provider": "gigachat",
                    "content": content,
                }
            except Exception:
                pass
        return {
            "provider": "local",
            "content": self._answer_locally(question=question, contexts=contexts),
        }

    def _answer_with_gigachat(
        self,
        *,
        question: str,
        history: list[dict[str, str]],
        contexts: list[dict[str, Any]],
    ) -> str:
        context_prompt = self._build_context_prompt(question=question, contexts=contexts)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context_prompt:
            messages.append({"role": "system", "content": context_prompt})
        for item in history[-6:]:
            role = item.get("role")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": item.get("content", "")})
        messages.append({"role": "user", "content": question})

        payload = {
            "model": self.gigachat_model,
            "temperature": 0.2,
            "max_tokens": 900,
            "messages": messages,
        }
        access_token = self._get_access_token()
        with httpx.Client(timeout=self.timeout_seconds, verify=self._verify_value()) as client:
            response = client.post(
                f"{self.gigachat_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("text")
            )
        content = (content or "").strip()
        if not content:
            raise RuntimeError("Empty response from GigaChat")
        return content

    def _get_access_token(self) -> str:
        if (
            self._access_token
            and self._access_token_expires_at
            and self._access_token_expires_at > datetime.now(UTC) + timedelta(minutes=2)
        ):
            return self._access_token

        with httpx.Client(timeout=self.timeout_seconds, verify=self._verify_value()) as client:
            response = client.post(
                self.gigachat_oauth_url,
                headers={
                    "Authorization": f"Basic {self.gigachat_auth_key}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={"scope": self.gigachat_scope},
            )
            response.raise_for_status()
            payload = response.json()

        access_token = payload.get("access_token")
        expires_at = payload.get("expires_at")
        if not access_token:
            raise RuntimeError("GigaChat access token missing in OAuth response")
        self._access_token = access_token
        self._access_token_expires_at = self._parse_token_expiration(expires_at)
        return access_token

    def _parse_token_expiration(self, raw_value: Any) -> datetime:
        if isinstance(raw_value, (int, float)):
            timestamp = float(raw_value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=UTC)
        return datetime.now(UTC) + timedelta(minutes=25)

    def _verify_value(self) -> str | bool:
        if self.ca_bundle:
            return self.ca_bundle
        if self.allow_insecure_ssl:
            return False
        return True

    def _build_context_prompt(self, *, question: str, contexts: list[dict[str, Any]]) -> str:
        if not contexts:
            return (
                "По запросу пользователя не найдено подтверждённого контекста в базе новостей. "
                "Нужно честно сообщить об этом и предложить уточнить муниципалитет, отрасль или период."
            )
        chunks = []
        for index, context in enumerate(contexts, start=1):
            sources = "\n".join(
                f"- {source['source_name']} | {source['published_at']} | {source['url']}\n  {source['snippet']}"
                for source in context.get("sources", [])[:3]
            )
            chunks.append(
                (
                    f"[{index}] Тема: {context['title']}\n"
                    f"Муниципалитет: {context['municipality']}\n"
                    f"Отрасль: {context['sector']}\n"
                    f"Последнее обновление: {context['last_seen']}\n"
                    f"Сводка: {context['summary']}\n"
                    f"Причины важности: {context['why']}\n"
                    f"Источники:\n{sources}"
                )
            )
        return (
            f"Вопрос пользователя: {question}\n\n"
            "Ниже контекст из системы мониторинга. Отвечай только по нему. "
            "Если используешь тему, упоминай её название и муниципалитет. "
            "После ответа добавь короткий блок «Источники», перечислив номера контекстов вроде [1], [2].\n\n"
            + "\n\n".join(chunks)
        )

    def _answer_locally(self, *, question: str, contexts: list[dict[str, Any]]) -> str:
        if not contexts:
            return (
                "По текущим данным системы я не нашёл подтверждённых материалов по этому запросу. "
                "Уточни муниципалитет, сферу проблемы или период, и я попробую сузить поиск."
            )

        lead = contexts[0]
        lines = [
            f"По данным «Сигнала» сейчас наиболее релевантная тема — {lead['title']} ({lead['municipality']}).",
            f"Кратко: {lead['summary']}",
        ]
        if len(contexts) > 1:
            lines.append("Также в релевантной выборке есть ещё сюжеты:")
            for item in contexts[1:3]:
                lines.append(
                    f"- {item['title']} ({item['municipality']}), последнее обновление {item['last_seen']}."
                )
        lines.append("Источники:")
        for index, item in enumerate(contexts[:3], start=1):
            source = item.get("sources", [{}])[0]
            lines.append(
                f"[{index}] {item['title']} — {source.get('source_name', 'источник')} ({source.get('published_at', item['last_seen'])})"
            )
        lines.append(f"Запрос: {shorten(question, 140)}")
        return "\n".join(lines)
