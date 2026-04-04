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
