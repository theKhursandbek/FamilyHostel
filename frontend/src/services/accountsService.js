import api from "./api";

/**
 * Account / role management API client (Super Admin only for writes).
 *
 * Backend wraps responses as `{success, data: {...}}`. We unwrap once here so
 * callers receive the plain payload (account object or paginated list).
 */

const BASE = "/auth/accounts/";

function unwrap(response) {
  const body = response?.data;
  if (body && typeof body === "object" && "data" in body) return body.data;
  return body;
}

/**
 * @param {{ role?: string, is_active?: boolean, search?: string }} [params]
 */
export async function listAccounts(params = {}) {
  const response = await api.get(BASE, { params });
  const data = unwrap(response);
  return data?.results ?? data ?? [];
}

export async function getAccount(id) {
  const response = await api.get(`${BASE}${id}/`);
  return unwrap(response);
}

/**
 * Create a new account with a role + role-specific data.
 *
 * payload shape:
 *   {
 *     phone: string,
 *     password: string,
 *     role_input: "staff" | "administrator" | "director" | "superadmin",
 *     full_name_input: string,
 *     branch?: number,
 *     salary_input?: number,
 *     telegram_chat_id?: string,
 *   }
 */
export async function createAccount(payload) {
  const response = await api.post(BASE, payload);
  return unwrap(response);
}

/**
 * Patch editable fields: phone, password, full_name_input, salary_input,
 * is_active, telegram_chat_id. Role is immutable (delete + recreate).
 */
export async function updateAccount(id, payload) {
  const response = await api.patch(`${BASE}${id}/`, payload);
  return unwrap(response);
}

export async function deleteAccount(id) {
  await api.delete(`${BASE}${id}/`);
}

export async function disableAccount(id) {
  const response = await api.post(`${BASE}${id}/disable/`);
  return unwrap(response);
}

export async function enableAccount(id) {
  const response = await api.post(`${BASE}${id}/enable/`);
  return unwrap(response);
}

/** GET /api/v1/branches/ — used to populate the branch dropdown. */
export async function listBranches() {
  const response = await api.get("/branches/branches/");
  const data = unwrap(response);
  return data?.results ?? data ?? [];
}
