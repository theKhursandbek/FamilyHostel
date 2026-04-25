import axios from "axios";
import { getAccessToken, refreshToken, logout } from "./auth";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor — attach Authorization header
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor — handle 401 with token refresh
let isRefreshing = false;
let failedQueue = [];

function processQueue(error, token = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });
  failedQueue = [];
}

// Auto-unwrap the backend's `{success: true, data: ...}` envelope so callers
// can keep using `response.data.<field>` regardless of the StandardJSONRenderer.
// Error responses ({success:false, error:{...}}) are left untouched so existing
// `err.response?.data?.detail` checks keep working via the rejection branch.
function unwrapEnvelope(response) {
  const body = response?.data;
  if (
    body &&
    typeof body === "object" &&
    body.success === true &&
    "data" in body
  ) {
    response.data = body.data;
  }
  return response;
}

// Normalise error envelopes so existing `err.response?.data?.detail` checks
// surface the real backend message instead of the fallback string.
function normaliseError(error) {
  const body = error?.response?.data;
  if (body && typeof body === "object" && body.success === false && body.error) {
    const { message, code, details } = body.error;
    error.response.data = {
      ...body,
      detail: message || code || "Request failed",
      message,
      code,
      details,
    };
  }
  return error;
}

api.interceptors.response.use(
  (response) => unwrapEnvelope(response),
  async (error) => {
    const originalRequest = error.config;

    // Only attempt refresh on 401, and not on login/refresh endpoints
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login/") &&
      !originalRequest.url?.includes("/auth/token/refresh/")
    ) {
      if (isRefreshing) {
        // Queue requests while refreshing
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const newToken = await refreshToken();
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        logout();
        globalThis.location.href = "/login";
        throw refreshError;
      } finally {
        isRefreshing = false;
      }
    }

    throw normaliseError(error);
  }
);

export default api;
