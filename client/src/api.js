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

// A student in an ATLAS study comes with ATLAS's signed ticket, which every call carries.
let ticket = null;
export function setStudyTicket(value) {
  ticket = value;
}

// One spoken line from the tutor's voice. The tutor's player fetches it without headers, so a study
// student's ticket rides in the link, as on the check-in stream.
export function speechUrl(text) {
  const query = new URLSearchParams({ text, ...(ticket ? { ticket } : {}) });
  return `/v1/tts?${query}`;
}

// Whether the page is at /name, with or without a trailing slash. The Research view is at
// /research, for the team only. ATLAS frames /study for a student a researcher gave the agent.
export function onPath(name, path = window.location.pathname) {
  return path.replace(/\/+$/, "") === `/${name}`;
}

// The student ATLAS's ticket names, from /study#ticket=... The server checks the signature,
// so this only reads who it says.
export function studyStudent(hash = window.location.hash) {
  const value = new URLSearchParams(hash.slice(1)).get("ticket");
  if (!value) return null;
  try {
    const body = value.split(".")[0].replace(/-/g, "+").replace(/_/g, "/");
    const data = JSON.parse(atob(body + "=".repeat((4 - (body.length % 4)) % 4)));
    if (!data.participant || !data.code) return null;
    return {
      environment: "zany-study",
      studentId: String(data.participant),
      classCode: String(data.code),
      ticket: value,
    };
  } catch {
    return null;
  }
}

async function request(path, { method = "GET", body, query, form } = {}) {
  const url = new URL(`/v1${path}`, window.location.origin);
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== null && value !== undefined && value !== "") url.searchParams.set(key, value);
  }
  const response = await fetch(url, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(ticket ? { "X-Study-Ticket": ticket } : {}),
    },
    body: form ?? (body === undefined ? undefined : JSON.stringify(body)),
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
  // The student's check-ins as they happen (server-sent events), or null where there is no
  // EventSource. The browser reconnects on its own after a drop.
  checkins: (student, onCheckin) => {
    if (typeof EventSource === "undefined") return null;
    const url = new URL(`/v1${studentPath(student)}/stream`, window.location.origin);
    if (student.classCode) url.searchParams.set("class_code", student.classCode);
    if (ticket) url.searchParams.set("ticket", ticket);
    const source = new EventSource(url);
    source.addEventListener("checkin", (event) => {
      try {
        onCheckin(JSON.parse(event.data));
      } catch {
        // A frame that is not JSON is skipped.
      }
    });
    return source;
  },
  transcribe: (student, recording) => {
    const form = new FormData();
    form.append("audio", recording, "question.webm");
    return request(`${studentPath(student)}/transcriptions`, {
      method: "POST",
      form,
      query: studentQuery(student),
    });
  },
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
