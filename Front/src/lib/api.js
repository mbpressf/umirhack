const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const buildUrl = (path) => `${API_BASE}${path}`;

export async function fetchFrontendSnapshot(signal) {
  const response = await fetch(buildUrl("/api/frontend-snapshot"), {
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Frontend snapshot request failed with ${response.status}`);
  }

  return response.json();
}

export async function fetchMetadata(signal) {
  const response = await fetch(buildUrl("/api/metadata"), {
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Metadata request failed with ${response.status}`);
  }

  return response.json();
}

export async function registerUser(payload) {
  const response = await fetch(buildUrl("/api/auth/register"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка регистрации. Попробуйте позже.");
  }
  return data;
}

export async function loginUser(payload) {
  const response = await fetch(buildUrl("/api/auth/login"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка входа. Попробуйте позже.");
  }
  return data;
}

export async function fetchChatStatus(signal) {
  const response = await fetch(buildUrl("/api/chat/status"), {
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat status request failed with ${response.status}`);
  }

  return response.json();
}

export async function fetchChatSessions(userId, signal) {
  const response = await fetch(buildUrl(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`), {
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось загрузить список диалогов.");
  }
  return data;
}

export async function fetchChatSession(userId, sessionId, signal) {
  const response = await fetch(buildUrl(`/api/chat/sessions/${sessionId}?user_id=${encodeURIComponent(userId)}`), {
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось загрузить историю диалога.");
  }
  return data;
}

export async function sendChatMessage(payload) {
  const response = await fetch(buildUrl("/api/chat/ask"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось получить ответ ассистента.");
  }
  return data;
}

