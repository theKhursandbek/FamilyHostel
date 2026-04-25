import api from "./api";

/**
 * CEO (SuperAdmin) management endpoints.
 *
 * Backend mounts these under /api/v1/admin-panel/ and /api/v1/.
 * The global response interceptor strips the {success,data} envelope,
 * so callers receive the plain payload.
 */

const SETTINGS = "/admin-panel/system-settings/";
const RULES = "/admin-panel/income-rules/";
const OVERRIDES = "/admin-panel/overrides/";
const ROLE_PEOPLE = "/admin-panel/role-people/";
const AUDIT_LOGS = "/audit-logs/";
const SUSPICIOUS = "/suspicious-activities/";

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
// Override (logged)
// ---------------------------------------------------------------------------
export async function performOverride(payload) {
  const { data } = await api.post(OVERRIDES, payload);
  return data;
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

// ---------------------------------------------------------------------------
// Activity / monitoring
// ---------------------------------------------------------------------------
export async function listAuditLogs(params = {}) {
  const { data } = await api.get(AUDIT_LOGS, { params });
  return data?.results ?? data ?? [];
}

/**
 * Paginated audit-log fetch — returns the full envelope with metadata
 * ({ count, total_pages, page, page_size, next, previous, results }).
 */
export async function listAuditLogsPaged(params = {}) {
  const { data } = await api.get(AUDIT_LOGS, { params });
  if (Array.isArray(data)) {
    return {
      results: data,
      count: data.length,
      page: 1,
      page_size: data.length,
      total_pages: 1,
      next: null,
      previous: null,
    };
  }
  return data;
}

export async function getAuditLogFacets() {
  const { data } = await api.get(`${AUDIT_LOGS}facets/`);
  return data ?? { roles: [], actions: [], entity_types: [] };
}

/**
 * Reverse a previously-recorded audit row. The backend re-applies
 * ``before_data`` to the live entity and writes a new audit row tagged
 * ``<original_action>.undone``. Throws if the row is not reversible
 * (`code: not_reversible`) or a newer change blocks the restore
 * (`code: conflict`).
 */
export async function undoAuditLog(id) {
  const { data } = await api.post(`${AUDIT_LOGS}${id}/undo/`);
  return data;
}

/** Re-apply a previously undone audit row. */
export async function redoAuditLog(id) {
  const { data } = await api.post(`${AUDIT_LOGS}${id}/redo/`);
  return data;
}

export async function listSuspiciousActivities(params = {}) {
  const { data } = await api.get(SUSPICIOUS, { params });
  return data?.results ?? data ?? [];
}
