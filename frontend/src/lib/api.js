import axios from "axios";

// Prefer same-origin to avoid cross-origin cookie issues; fall back to env var.
const ENV_URL = process.env.REACT_APP_BACKEND_URL;
const BACKEND_URL = (typeof window !== "undefined" && window.location && window.location.origin)
  ? window.location.origin
  : ENV_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export function formatApiError(detail, fallback = "Algo correu mal. Tente novamente.") {
  if (detail == null) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  }
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
