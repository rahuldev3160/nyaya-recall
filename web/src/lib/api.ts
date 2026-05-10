const BASE =
  typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000`
    : "http://localhost:8000";

async function post(path: string, body: object = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function get(path: string) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
};
