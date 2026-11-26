// The API, same-origin under /v1. A student is { environment, studentId, classCode }.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI says what went wrong as a string, or as a list of field errors.
function describe(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg).join(" ");
  return `The agent answered with an error (${status}).`;
}

async function request(path, { method = "GET", body, query } = {}) {
  const url = new URL(`/v1${path}`, window.location.origin);
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== null && value !== undefined && value !== "") url.searchParams.set(key, value);
  }
  const response = await fetch(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // The Turnstile gate wants a solved challenge first. TurnstileGate shows it.
    if (response.status === 403 && data.error === "turnstile_required") {
      window.dispatchEvent(new CustomEvent("turnstile:required"));
    }
    throw new ApiError(describe(data.detail, response.status), response.status);
  }
  return data;
}

const studentPath = (s) => `/${s.environment}/students/${encodeURIComponent(s.studentId)}`;
const studentQuery = (s) => ({ class_code: s.classCode });

export const api = {
  ping: () => request("/ping"),
  environments: () => request("/environments"),
  researchConfig: () => request("/research/config"),
  signIn: (student, chat) =>
    request(studentPath(student), { query: { ...studentQuery(student), chat } }),
  turn: (student, body) =>
    request(`${studentPath(student)}/turns`, {
      method: "POST",
      body,
      query: studentQuery(student),
    }),
  rate: (student, body) =>
    request(`${studentPath(student)}/ratings`, {
      method: "POST",
      body,
      query: studentQuery(student),
    }),
  saveSettings: (student, overrides) =>
    request(`${studentPath(student)}/settings`, {
      method: "PUT",
      body: { overrides },
      query: studentQuery(student),
    }),
};

// Small persistence helpers. A sign-in lives for the tab (sessionStorage), so a shared classroom
// computer forgets the student when the tab closes. Preferences live in localStorage.
export function readStored(storage, key, fallback) {
  try {
    const raw = storage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function writeStored(storage, key, value) {
  try {
    if (value === null || value === undefined) storage.removeItem(key);
    else storage.setItem(key, JSON.stringify(value));
  } catch {
    // A browser with storage off still works, it just forgets on reload.
  }
}
