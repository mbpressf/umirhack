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

