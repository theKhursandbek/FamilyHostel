import axios from "axios";

/**
 * Authentication service for the Telegram Mini App.
 *
 * Two flows:
 *   1. Telegram (production)  → POST /auth/telegram/  with initData
 *   2. Phone+password (dev)   → POST /auth/login/     fallback for
 *      browser-based testing when there's no Telegram SDK present.
 *
 * Tokens are persisted in localStorage and consumed by api.js.
 */

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const TOKEN_KEY = "tg_access";
const REFRESH_KEY = "tg_refresh";
const USER_KEY = "tg_user";

/* ---------------------------------------------------------------------------
 * Storage helpers (kept synchronous so React renders can inspect them)
 * ------------------------------------------------------------------------- */

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function hasToken() {
  return !!localStorage.getItem(TOKEN_KEY);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

function persist({ access, refresh, user }) {
  localStorage.setItem(TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function unwrap(payload) {
  return payload?.data ?? payload;
}

/* ---------------------------------------------------------------------------
 * Flows
 * ------------------------------------------------------------------------- */

/**
 * Exchange Telegram WebApp `initData` for a JWT pair.
 *
 * The backend returns: `{account_id, telegram_id, roles, is_new, access, refresh}`.
 * We normalise into a `user` object similar to the admin panel's shape.
 */
export async function loginWithTelegram(initData) {
  const response = await axios.post(`${API_URL}/auth/telegram/`, { init_data: initData });
  const body = unwrap(response.data);
  const user = {
    id: body.account_id,
    telegram_id: body.telegram_id,
    roles: body.roles || [],
    is_new: body.is_new,
  };
  persist({ access: body.access, refresh: body.refresh, user });
  return user;
}

/**
 * Dev/demo fallback — phone + password against the admin login endpoint.
 * Intended for testing the staff/client UI in a regular browser. Disabled
 * when `VITE_DEV_FALLBACK_LOGIN` is not "true".
 */
export async function loginWithPhone(phone, password) {
  const response = await axios.post(`${API_URL}/auth/login/`, { phone, password });
  const body = unwrap(response.data);
  persist({ access: body.access, refresh: body.refresh, user: body.user });
  return body.user;
}

export async function refreshToken() {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) throw new Error("no refresh token");
  const response = await axios.post(`${API_URL}/auth/token/refresh/`, { refresh });
  const body = unwrap(response.data);
  localStorage.setItem(TOKEN_KEY, body.access);
  if (body.refresh) localStorage.setItem(REFRESH_KEY, body.refresh);
  return body.access;
}
