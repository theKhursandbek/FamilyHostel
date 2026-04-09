import api from "./api";

const TOKEN_KEY = "access_token";
const REFRESH_KEY = "refresh_token";
const USER_KEY = "user";

/**
 * Login with phone + password.
 * Stores tokens and user data in localStorage.
 */
export async function login(phone, password) {
  const response = await api.post("/auth/login/", { phone, password });
  // Backend wraps responses: { success: true, data: { access, refresh, user } }
  const payload = response.data.data || response.data;
  const { access, refresh, user } = payload;

  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
  localStorage.setItem(USER_KEY, JSON.stringify(user));

  return { access, refresh, user };
}

/**
 * Refresh the access token using the stored refresh token.
 */
export async function refreshToken() {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) {
    throw new Error("No refresh token available");
  }

  const response = await api.post("/auth/token/refresh/", { refresh });
  // Backend wraps responses: { success: true, data: { access, ... } }
  const payload = response.data.data || response.data;
  const { access } = payload;

  localStorage.setItem(TOKEN_KEY, access);

  // If the backend rotates refresh tokens, store the new one
  if (payload.refresh) {
    localStorage.setItem(REFRESH_KEY, payload.refresh);
  }

  return access;
}

/**
 * Logout — clear all stored auth data.
 */
export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Get the stored access token.
 */
export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Get the stored user data.
 */
export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Check if user has a stored token (may be expired).
 */
export function hasToken() {
  return !!localStorage.getItem(TOKEN_KEY);
}
