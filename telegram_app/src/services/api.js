import axios from "axios";
import { getAccessToken, refreshToken, logout } from "./auth";

/**
 * Shared axios instance for the Telegram Mini App.
 *
 * - Attaches the JWT access token from localStorage on every request.
 * - On 401, tries one silent refresh, queues concurrent failures, and
 *   bounces to /login (which shows the Telegram-auth handshake) on failure.
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let isRefreshing = false;
let queue = [];

function flush(error, token = null) {
  queue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token)));
  queue = [];
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queue.push({ resolve, reject });
        }).then((tok) => {
          original.headers.Authorization = `Bearer ${tok}`;
          return api(original);
        });
      }
      original._retry = true;
      isRefreshing = true;
      try {
        const tok = await refreshToken();
        flush(null, tok);
        original.headers.Authorization = `Bearer ${tok}`;
        return api(original);
      } catch (e) {
        flush(e, null);
        logout();
        globalThis.location.href = "/login";
        throw e;
      } finally {
        isRefreshing = false;
      }
    }
    throw error;
  }
);

/**
 * Backend wraps responses as `{success, data}` via StandardJSONRenderer.
 * This helper unwraps once so callers always work with the inner payload.
 */
export function unwrap(response) {
  const body = response?.data;
  if (body && typeof body === "object" && "data" in body) return body.data;
  return body;
}

export default api;
