// All calls go through the Next.js proxy (/api/backend → port 8000).
const BASE = "/api/backend";

async function post(path: string, body: object = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function get(path: string, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { signal: ctrl.signal });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  generateQuiz: (config: object) => post("/quiz/generate", config),
  submitAnswer: (answer: object) => post("/sessions/answer", answer),
  closeSession: (id: string) => post(`/sessions/${id}/close`),
  importSession: (data: object) => post("/sessions/import", data),
  syncAnalysis: () => post("/analysis/sync"),
  getPlan: () => get("/plan/today"),
  generatePlan: (hours: number) => post("/plan/generate", { available_hours: hours }),
  getProfile: () => get("/tracker/profile"),
  getSubjects: () => get("/tracker/subjects"),
  getSubtopics: (subjectId: string) => get(`/tracker/subtopics/${subjectId}`),
  getGaps: () => get("/tracker/gaps"),
  getSar: () => get("/tracker/sar"),
  getConfig: () => get("/config"),
  saveConfig: (config: object) => post("/config", config),
  submitAttestation: (body: object) => post("/attestation/claim", body),
  validateAttestation: (body: object) => post("/attestation/validate", body),
  expandConcept: (body: object) => post("/sessions/expand-concept", body),
  expandNotesSelection: (body: object) => post("/sessions/expand-notes-selection", body),
  getUserNotes: (sessionId: string) => get(`/sessions/${sessionId}/user-notes`),
  getRevisionNotes: (sessionId: string) => post(`/sessions/${sessionId}/revision-notes`),
  putUserNotes: (sessionId: string, body: object) =>
    fetch(`${BASE}/sessions/${sessionId}/user-notes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(async (res) => {
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }),
  getSessionHistory: (limit = 30) => get(`/sessions/?limit=${limit}`),
  getSession: (id: string) => get(`/sessions/${id}`),
  getTimeStats: () => get("/tracker/time-stats"),
};
