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
 *     branch?: number,                  // required for staff/admin/director
 *     is_general_manager_input?: boolean, // director only — extra bonus + personal report
 *     telegram_chat_id?: string,
 *   }
 *
 * Salary is no longer set at creation; it is computed from base wage rules
 * (Branch.working_days_per_month × per-shift rate) plus adjustments.
 */
export async function createAccount(payload) {
  const response = await api.post(BASE, payload);
  return unwrap(response);
}

/**
 * Patch editable fields: phone, password, full_name_input,
 * is_general_manager_input (director only), is_active, telegram_chat_id.
 * Role is immutable (delete + recreate).
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

/**
 * GET /auth/accounts/branches-available-for-director/ — branches that have NO
 * active director yet. Used by the user-create modal to enforce the
 * one-director-per-branch invariant at the UI level (the backend also enforces
 * it via a partial unique constraint).
 *
 * @returns {Promise<Array<{id: number, name: string}>>}
 */
export async function listBranchesAvailableForDirector() {
  const response = await api.get(`${BASE}branches-available-for-director/`);
  const data = unwrap(response);
  return data?.results ?? data ?? [];
}
