import axios from "axios";

// In Docker: browser calls go to Vite dev server (/api/*) 
// which proxies to backend container. Outside Docker: direct to localhost:8000
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ims_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("ims_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// ── Auth ──────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post("/auth/login", { username, password });

export const register = (username, email, password) =>
  api.post("/auth/register", { username, email, password });

// ── Incidents ─────────────────────────────────────────────────
export const getIncidents = (params) => api.get("/incidents", { params });
export const getIncident  = (id)     => api.get(`/incidents/${id}`);
export const transitionState = (id, to_status, note) =>
  api.patch(`/incidents/${id}/state`, { to_status, note });

// ── RCA ───────────────────────────────────────────────────────
export const submitRCA = (id, payload) => api.post(`/incidents/${id}/rca`, payload);

// ── Signals ───────────────────────────────────────────────────
export const ingestSignal = (payload) => api.post("/signals", payload);
