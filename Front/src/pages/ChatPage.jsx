import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchChatSession,
  fetchChatSessions,
  fetchChatStatus,
  sendChatMessage,
} from "../lib/api";

const AUTH_STORAGE_KEY = "signal:auth-user";

function readAuthUser() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

function formatMessageTime(value) {
  if (!value) {
    return "";
  }

  try {
    return new Date(value).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (error) {
    return value;
  }
}

const COPY = {
  ru: {
    title: "AI-ассистент по региону",
    subtitle:
      "Задавайте вопросы по новостям, проблемам, муниципалитетам и подтвержденным темам. Ассистент отвечает по данным системы и прикладывает источники.",
    modeLive: "LLM + поиск по данным",
    modeFallback: "Поиск по данным + локальный ответ",
    providerLive: "GigaChat подключен",
    providerFallback: "Локальный безопасный режим",
    providerLiveHint: "Ответы строятся на базе тем, карточек проблем и источников из вашей системы.",
    providerFallbackHint:
      "Чат сейчас работает без внешнего LLM-ключа, но все равно опирается на данные платформы и возвращает источники.",
    newSession: "Новый диалог",
    emptySessions: "Пока нет диалогов. Начните с вопроса о городе, проблеме или источниках подтверждения.",
    emptyMessages:
      "Спросите, что сейчас происходит в Таганроге, какие темы официально подтверждены или где в области самая напряженная ситуация.",
    loadingSessions: "Загружаем диалоги...",
    loadingMessages: "Загружаем историю...",
    sessionsTitle: "Диалоги",
    sessionsSubtitle: "История вопросов и ответов",
    composerPlaceholder:
      "Например: Какие проблемы сейчас самые заметные в Батайске и что подтверждено официально?",
    composerHint: "Ассистент отвечает только по данным сайта и прикладывает источники.",
    send: "Отправить",
    sending: "Отправляем...",
    openProfile: "Открыть профиль",
    authTitle: "Войдите, чтобы открыть AI-ассистента",
    authText:
      "После входа можно сохранять историю диалогов, спрашивать по муниципалитетам, темам и получать ответы с источниками.",
    authFeature1: "Ответы по новостям и карточкам проблем",
    authFeature2: "Ссылки на источники в каждом ответе",
    authFeature3: "История диалогов для каждого пользователя",
    sources: "Источники",
    suggestionsTitle: "Быстрые вопросы",
    suggestions: [
      "Что сейчас происходит в Ростове-на-Дону?",
      "Какие темы по Батайску подтверждены официально?",
      "Где самые критичные сигналы за последние дни?",
      "Какие проблемы чаще всего встречаются в транспортной сфере?",
    ],
    askAbout: "Что можно спросить",
    askAboutItems: [
      "Муниципалитет: Ростов-на-Дону, Батайск, Таганрог, Волгодонск",
      "Проблема: отключения, ДТП, МФЦ, коммунальные сбои",
      "Подтверждение: какие темы подтверждены официально и какими источниками",
    ],
    assistantName: "Сигнал AI",
    fallbackLabel: "Fallback",
  },
  en: {
    title: "Regional AI assistant",
    subtitle:
      "Ask about news, issues, municipalities, and confirmed topics. The assistant answers from platform data and cites sources.",
    modeLive: "LLM + retrieval",
    modeFallback: "Retrieval + local answer",
    providerLive: "GigaChat connected",
    providerFallback: "Local safe mode",
    providerLiveHint: "Answers are grounded in topics, issue cards, and source evidence from the platform.",
    providerFallbackHint:
      "The assistant currently runs without an external LLM key, but still answers from platform data and returns sources.",
    newSession: "New chat",
    emptySessions: "No chats yet. Start with a question about a city, issue, or supporting sources.",
    emptyMessages:
      "Ask what is happening in Taganrog, which topics are officially confirmed, or where the strongest signals are right now.",
    loadingSessions: "Loading chats...",
    loadingMessages: "Loading history...",
    sessionsTitle: "Chats",
    sessionsSubtitle: "Saved conversation history",
    composerPlaceholder:
      "For example: What issues are currently most visible in Bataysk and which ones are officially confirmed?",
    composerHint: "The assistant answers only from your site data and includes sources.",
    send: "Send",
    sending: "Sending...",
    openProfile: "Open profile",
    authTitle: "Sign in to use the AI assistant",
    authText:
      "After signing in you can keep conversation history, ask about municipalities and topics, and get grounded answers with sources.",
    authFeature1: "Answers from issue cards and news topics",
    authFeature2: "Sources attached to every response",
    authFeature3: "Per-user chat history",
    sources: "Sources",
    suggestionsTitle: "Quick prompts",
    suggestions: [
      "What is happening in Rostov-on-Don right now?",
      "Which Bataysk topics are officially confirmed?",
      "Where are the most critical signals in the region this week?",
      "Which transport issues appear most often?",
    ],
    askAbout: "What to ask",
    askAboutItems: [
      "Municipality: Rostov-on-Don, Bataysk, Taganrog, Volgodonsk",
      "Issue: outages, accidents, public service delays, коммунальные сбои",
      "Confirmation: which topics are officially confirmed and by what sources",
    ],
    assistantName: "Signal AI",
    fallbackLabel: "Fallback",
  },
};

export default function ChatPage({ locale = "ru", onRequestLogin }) {
  const copy = COPY[locale] ?? COPY.ru;
  const [user, setUser] = useState(() => readAuthUser());
  const [chatStatus, setChatStatus] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const textareaRef = useRef(null);
  const messagesRef = useRef(null);

  useEffect(() => {
    const syncUser = () => setUser(readAuthUser());
    const onFocus = () => syncUser();
    const onStorage = (event) => {
      if (!event.key || event.key === AUTH_STORAGE_KEY) {
        syncUser();
      }
    };

    window.addEventListener("focus", onFocus);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchChatStatus(controller.signal)
      .then((payload) => setChatStatus(payload))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!user?.id) {
      setSessions([]);
      setMessages([]);
      setActiveSessionId(null);
      return undefined;
    }

    const controller = new AbortController();
    setLoadingSessions(true);
    setError("");

    fetchChatSessions(user.id, controller.signal)
      .then((payload) => {
        const items = payload.items ?? [];
        setSessions(items);
        setChatStatus(payload.status ?? null);
        setActiveSessionId((current) => {
          if (current && items.some((item) => item.id === current)) {
            return current;
          }
          return items[0]?.id ?? null;
        });
      })
      .catch((loadError) => {
        if (loadError.name !== "AbortError") {
          setError(loadError.message || copy.emptySessions);
        }
      })
      .finally(() => setLoadingSessions(false));

    return () => controller.abort();
  }, [copy.emptySessions, user?.id]);

  useEffect(() => {
    if (!user?.id || !activeSessionId) {
      setMessages([]);
      return undefined;
    }

    const controller = new AbortController();
    setLoadingMessages(true);
    setError("");

    fetchChatSession(user.id, activeSessionId, controller.signal)
      .then((payload) => {
        setMessages(payload.messages ?? []);
        setChatStatus(payload.status ?? null);
      })
      .catch((loadError) => {
        if (loadError.name !== "AbortError") {
          setError(loadError.message || copy.loadingMessages);
        }
      })
      .finally(() => setLoadingMessages(false));

    return () => controller.abort();
  }, [activeSessionId, copy.loadingMessages, user?.id]);

  useEffect(() => {
    const node = messagesRef.current;
    if (!node) {
      return;
    }

    node.scrollTo({
      top: node.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loadingMessages, sending]);

  const activeSession = useMemo(
    () => sessions.find((item) => item.id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  );

  const submitPrompt = async () => {
    const text = prompt.trim();
    if (!user?.id || !text || sending) {
      return;
    }

    setSending(true);
    setError("");
    try {
      const payload = await sendChatMessage({
        user_id: user.id,
        session_id: activeSessionId,
        message: text,
      });

      setPrompt("");
      setChatStatus(payload.status ?? null);
      setActiveSessionId(payload.session.id);
      setSessions((current) => {
        const next = current.filter((item) => item.id !== payload.session.id);
        return [payload.session, ...next];
      });
      setMessages((current) => {
        const isSameSession = activeSessionId === payload.session.id;
        if (!isSameSession) {
          return [payload.user_message, payload.assistant_message];
        }
        return [...current, payload.user_message, payload.assistant_message];
      });
      requestAnimationFrame(() => textareaRef.current?.focus());
    } catch (sendError) {
      setError(sendError.message || copy.providerFallbackHint);
    } finally {
      setSending(false);
    }
  };

  const handleSend = async (event) => {
    event.preventDefault();
    await submitPrompt();
  };

  const handleKeyDown = async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await submitPrompt();
    }
  };

  const applySuggestion = (value) => {
    setPrompt(value);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const startNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setPrompt("");
    setError("");
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  if (!user?.id) {
    return (
      <div className="page chat-page">
        <section className="card chat-auth-card animate-in">
          <div className="chat-auth-copy">
            <span className="section-kicker">AI</span>
            <h2>{copy.authTitle}</h2>
            <p>{copy.authText}</p>
            <ul className="chat-feature-list">
              <li>{copy.authFeature1}</li>
              <li>{copy.authFeature2}</li>
              <li>{copy.authFeature3}</li>
            </ul>
            <button type="button" className="primary-button" onClick={onRequestLogin}>
              {copy.openProfile}
            </button>
          </div>
          <div className="chat-auth-preview">
            <div className="chat-preview-bubble assistant">
              <strong>{copy.assistantName}</strong>
              <p>{copy.providerLiveHint}</p>
            </div>
            <div className="chat-preview-bubble user">
              <strong>User</strong>
              <p>{copy.suggestions[0]}</p>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page chat-page">
      <section className="card chat-hero animate-in">
        <div className="chat-hero-copy">
          <span className="section-kicker">AI</span>
          <h2>{copy.title}</h2>
          <p>{copy.subtitle}</p>
        </div>

        <div className="chat-hero-status">
          <div className="chat-status-badge">
            <span>{chatStatus?.provider === "gigachat" ? copy.modeLive : copy.modeFallback}</span>
            <strong>{chatStatus?.provider === "gigachat" ? copy.providerLive : copy.providerFallback}</strong>
          </div>
          <div className="chat-status-note">
            {chatStatus?.provider === "gigachat" ? copy.providerLiveHint : copy.providerFallbackHint}
          </div>
        </div>
      </section>

      <section className="chat-page-grid">
        <aside className="card chat-panel chat-sessions-panel animate-in">
          <div className="section-head">
            <div>
              <h3>{copy.sessionsTitle}</h3>
              <span>{copy.sessionsSubtitle}</span>
            </div>
            <button type="button" className="secondary-button" onClick={startNewSession}>
              {copy.newSession}
            </button>
          </div>

          <div className="chat-session-list">
            {loadingSessions && !sessions.length ? (
              <div className="chat-session-placeholder">{copy.loadingSessions}</div>
            ) : null}

            {!loadingSessions && !sessions.length ? (
              <div className="chat-session-placeholder">{copy.emptySessions}</div>
            ) : null}

            {sessions.map((session) => (
              <button
                type="button"
                key={session.id}
                className={`chat-session-item ${activeSessionId === session.id ? "active" : ""}`}
                onClick={() => setActiveSessionId(session.id)}
              >
                <strong>{session.title}</strong>
                <small>{formatMessageTime(session.updated_at)}</small>
                {session.last_message_preview ? <span>{session.last_message_preview}</span> : null}
              </button>
            ))}
          </div>
        </aside>

        <section className="card chat-panel chat-conversation-panel animate-in">
          <div className="chat-conversation-head">
            <div>
              <strong>{activeSession?.title ?? copy.newSession}</strong>
              <span>{activeSession ? formatMessageTime(activeSession.updated_at) : copy.modeFallback}</span>
            </div>
            <div className={`chat-mode-badge ${chatStatus?.provider === "gigachat" ? "live" : "fallback"}`}>
              {chatStatus?.provider === "gigachat" ? "LLM" : copy.fallbackLabel}
            </div>
          </div>

          <div ref={messagesRef} className="chat-message-list">
            {loadingMessages && !messages.length ? (
              <div className="chat-empty-placeholder">{copy.loadingMessages}</div>
            ) : null}

            {!loadingMessages && !messages.length ? (
              <div className="chat-empty-placeholder">
                <p>{copy.emptyMessages}</p>
              </div>
            ) : null}

            {messages.map((message) => (
              <article
                key={message.id}
                className={`chat-message ${message.role === "assistant" ? "assistant" : "user"}`}
              >
                <div className="chat-message-meta">
                  <strong>{message.role === "assistant" ? copy.assistantName : user.login}</strong>
                  <span>{formatMessageTime(message.created_at)}</span>
                </div>
                <p>{message.content}</p>

                {message.citations?.length > 0 ? (
                  <div className="chat-citations">
                    <h4>{copy.sources}</h4>
                    {message.citations.map((citation, index) => (
                      <a
                        key={`${message.id}-${citation.url}-${index}`}
                        className="chat-citation"
                        href={citation.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <strong>{citation.title}</strong>
                        <span>
                          {citation.municipality || "unknown"} · {citation.source_name}
                        </span>
                        <small>{citation.snippet}</small>
                      </a>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>

          <form className="chat-compose" onSubmit={handleSend}>
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={copy.composerPlaceholder}
              rows={4}
            />

            <div className="chat-compose-actions">
              <span className="chat-compose-hint">{copy.composerHint}</span>
              <button type="submit" className="primary-button" disabled={sending || !prompt.trim()}>
                {sending ? copy.sending : copy.send}
              </button>
            </div>
          </form>

          {error ? <div className="auth-error chat-error">{error}</div> : null}
        </section>

        <aside className="card chat-panel chat-context-panel animate-in">
          <div className="section-head">
            <div>
              <h3>{copy.suggestionsTitle}</h3>
              <span>{copy.askAbout}</span>
            </div>
          </div>

          <div className="chat-suggestion-list">
            {copy.suggestions.map((item) => (
              <button
                type="button"
                key={item}
                className="chat-suggestion-chip"
                onClick={() => applySuggestion(item)}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="chat-tip-stack">
            {copy.askAboutItems.map((item) => (
              <div key={item} className="chat-tip-card">
                {item}
              </div>
            ))}
          </div>
        </aside>
      </section>
    </div>
  );
}
