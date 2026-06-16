import api from "./api";

/**
 * CEO (SuperAdmin) management endpoints.
 *
 * Backend mounts these under /api/v1/admin-panel/.
 * The global response interceptor strips the {success,data} envelope,
 * so callers receive the plain payload.
 */

const SETTINGS = "/admin-panel/system-settings/";
const RULES = "/admin-panel/income-rules/";
const ROLE_PEOPLE = "/admin-panel/role-people/";

// ---------------------------------------------------------------------------
// System settings (singleton)
// ---------------------------------------------------------------------------
export async function getSystemSettings() {
  const { data } = await api.get(SETTINGS);
  return data;
}

export async function updateSystemSettings(payload) {
  const { data } = await api.patch(SETTINGS, payload);
  return data;
}

// ---------------------------------------------------------------------------
// Income rules
// ---------------------------------------------------------------------------
export async function listIncomeRules(params = {}) {
  const { data } = await api.get(RULES, { params });
  return data?.results ?? data ?? [];
}

export async function createIncomeRule(payload) {
  const { data } = await api.post(RULES, payload);
  return data;
}

export async function updateIncomeRule(id, payload) {
  const { data } = await api.patch(`${RULES}${id}/`, payload);
  return data;
}

export async function deleteIncomeRule(id) {
  await api.delete(`${RULES}${id}/`);
}

// ---------------------------------------------------------------------------
// Per-person salary overrides
// ---------------------------------------------------------------------------
export async function listRolePeople(role, params = {}) {
  const { data } = await api.get(`${ROLE_PEOPLE}${role}/`, { params });
  return data ?? [];
}

export async function updateRolePersonSalary(role, id, salaryOverride) {
  const { data } = await api.patch(`${ROLE_PEOPLE}${role}/${id}/`, {
    salary_override: salaryOverride,
  });
  return data;
}
