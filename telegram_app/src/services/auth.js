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

export async function refreshToken() {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) throw new Error("no refresh token");
  const response = await axios.post(`${API_URL}/auth/token/refresh/`, { refresh });
  const body = unwrap(response.data);
  localStorage.setItem(TOKEN_KEY, body.access);
  if (body.refresh) localStorage.setItem(REFRESH_KEY, body.refresh);
  return body.access;
}

/**
 * Complete a brand-new client's profile (full name, phone, language).
 * Called from the onboarding screen for first-time Telegram users.
 */
export async function completeProfile({ full_name, phone, language }) {
  const token = getAccessToken();
  const response = await axios.post(
    `${API_URL}/auth/profile/`,
    { full_name, phone, language },
    { headers: { Authorization: `Bearer ${token}` } },
  );
  const body = unwrap(response.data);
  // Merge into stored user blob so the rest of the app sees the new fields.
  const stored = getStoredUser() || {};
  const merged = { ...stored, ...body, is_new: false };
  localStorage.setItem(USER_KEY, JSON.stringify(merged));
  return merged;
}

/**
 * Update profile fields (any subset of: first_name, last_name, full_name,
 * date_of_birth, phone, passport_number, language). POSTs to the same
 * /auth/profile/ endpoint, which now accepts the extended payload.
 */
export async function updateProfile(payload) {
  const token = getAccessToken();
  const response = await axios.post(
    `${API_URL}/auth/profile/`,
    payload,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  const body = unwrap(response.data);
  const stored = getStoredUser() || {};
  const merged = { ...stored, ...body, is_new: false };
  localStorage.setItem(USER_KEY, JSON.stringify(merged));
  return merged;
}

/** Re-fetch the current account profile (post-login refresh). */
export async function getMe() {
  const token = getAccessToken();
  if (!token) return null;
  const response = await axios.get(`${API_URL}/auth/me/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return unwrap(response.data);
}

/* ---------------------------------------------------------------------------
 * Password registration & login (Mini App clients)
 * ------------------------------------------------------------------------- */

/**
 * Register a new client (or upgrade an existing Telegram-only account).
 * Body fields: first_name, last_name, date_of_birth (YYYY-MM-DD),
 * passport_number, phone, password, confirm_password.
 */
export async function register(payload) {
  const headers = { "Content-Type": "application/json" };
  // If we already have a Telegram-issued token, send it so the backend
  // updates the existing account instead of creating a duplicate.
  const tok = getAccessToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const response = await axios.post(`${API_URL}/auth/register/`, payload, { headers });
  const body = unwrap(response.data);
  const user = _normalizeUser(body);
  persist({ access: body.access, refresh: body.refresh, user });
  return user;
}

/** Phone + password login. */
export async function loginWithPassword({ phone, password }) {
  const response = await axios.post(
    `${API_URL}/auth/client/login/`,
    { phone, password },
  );
  const body = unwrap(response.data);
  const user = _normalizeUser(body);
  persist({ access: body.access, refresh: body.refresh, user });
  return user;
}

/**
 * Send OTP via Telegram bot.
 * purpose: "register" | "change_password" | "forgot_password"
 * phone: required for "register" and "forgot_password"
 */
export async function sendTelegramOtp({ purpose, phone }) {
  const headers = { "Content-Type": "application/json" };
  const tok = getAccessToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const body = { purpose };
  if (phone) body.phone = phone;
  const response = await axios.post(`${API_URL}/auth/otp/telegram/send/`, body, { headers });
  return unwrap(response.data);
}

/** Authenticated password change — requires current password for verification. */
export async function changePassword({ current_password, new_password, confirm_password }) {
  const tok = getAccessToken();
  if (!tok) throw new Error("Not authenticated");
  const response = await axios.post(
    `${API_URL}/auth/password/change/`,
    { current_password, new_password, confirm_password },
    { headers: { Authorization: `Bearer ${tok}` } },
  );
  return unwrap(response.data);
}

/** Unauthenticated forgot-password reset — requires phone + OTP + new password. */
export async function resetPassword({ phone, code, new_password, confirm_password }) {
  const response = await axios.post(
    `${API_URL}/auth/password/reset/`,
    { phone, code, new_password, confirm_password },
  );
  const body = unwrap(response.data);
  // Store tokens so the user is auto-logged-in after reset.
  if (body.access) {
    localStorage.setItem("tg_access", body.access);
    if (body.refresh) localStorage.setItem("tg_refresh", body.refresh);
  }
  return body;
}

function _normalizeUser(body) {
  return {
    id: body.account_id,
    telegram_id: body.telegram_id,
    roles: body.roles || [],
    is_new: !!body.is_new,
    phone: body.phone || "",
    full_name: body.full_name || "",
    first_name: body.first_name || "",
    last_name: body.last_name || "",
    passport_number: body.passport_number || "",
    date_of_birth: body.date_of_birth || null,
    language: body.language || "uz",
  };
}
