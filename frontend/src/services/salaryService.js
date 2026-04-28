import api from "./api";

/** GET /payments/salary/ — list persisted salary records (history) */
export async function getSalaries(params = {}) {
  const response = await api.get("/payments/salary/", { params });
  return response.data;
}

/**
 * GET /payments/salary/preview/?account=&period_start=&period_end=
 * Live salary breakdown for a single account (without persisting).
 * Staff omits ``account`` to fetch their own.
 */
export async function previewSalary(params = {}) {
  const response = await api.get("/payments/salary/preview/", { params });
  return response.data;
}

/**
 * GET /payments/salary/roster/?branch=&period_start=&period_end=
 * Manager-only: branch payroll roster with live totals + locked record id.
 */
export async function getSalaryRoster(params = {}) {
  const response = await api.get("/payments/salary/roster/", { params });
  return response.data;
}

/**
 * POST /payments/salary/calculate/  — locks a SalaryRecord for the period.
 * Body: { account, period_start, period_end }
 */
export async function calculateSalary(payload) {
  const response = await api.post("/payments/salary/calculate/", payload);
  return response.data;
}

/** POST /payments/salary/{id}/mark-paid/ — flip a record to paid. */
export async function markSalaryPaid(id) {
  const response = await api.post(`/payments/salary/${id}/mark-paid/`);
  return response.data;
}

/**
 * PATCH /payments/salary/{id}/override/
 * Body: { amount, note? }. Director/CEO only. Audited.
 */
export async function overrideSalary(id, payload) {
  const response = await api.patch(`/payments/salary/${id}/override/`, payload);
  return response.data;
}

/** GET /payments/salary/{id}/audit/ — chronological audit trail. */
export async function getSalaryAudit(id) {
  const response = await api.get(`/payments/salary/${id}/audit/`);
  return response.data;
}

// ──────────── Calendar-driven payroll lifecycle (§3.3 / Q11) ────────────

/**
 * GET /payments/salary/lifecycle-status/
 * Returns advance/final window state, label-flip flags and the Q11
 * "previous month still unpaid" banner trigger.
 */
export async function getSalaryLifecycleStatus() {
  const response = await api.get("/payments/salary/lifecycle-status/");
  return response.data;
}

/**
 * POST /payments/salary/pay-advance/  — CEO only.
 * Body: { year, month }. Day 15–20 of month M only; otherwise 409.
 */
export async function payAdvance(payload) {
  const response = await api.post("/payments/salary/pay-advance/", payload);
  return response.data;
}

/**
 * POST /payments/salary/pay-final/  — CEO only.
 * Body: { year, month } (the period being paid is M). Day 1–5 of M+1.
 */
export async function payFinal(payload) {
  const response = await api.post("/payments/salary/pay-final/", payload);
  return response.data;
}

/**
 * POST /payments/salary/pay-late/  — CEO only (Q11).
 * Body: { year, month, reason }. Available only after the final window
 * has closed; written reason is mandatory.
 */
export async function payLate(payload) {
  const response = await api.post("/payments/salary/pay-late/", payload);
  return response.data;
}

/**
 * GET /payments/salary/roster/?export=csv&...
 * Triggers a browser download of the payroll CSV.
 * NOTE: we use ``export=csv`` (NOT ``format=csv``) because DRF reserves
 * the ``format`` query param for content-negotiation and would 404.
 */
export async function exportRosterCsv(params = {}) {
  const response = await api.get("/payments/salary/roster/", {
    params: { ...params, export: "csv" },
    responseType: "blob",
  });
  const blob = new Blob([response.data], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const filename =
    /filename="?([^"]+)"?/i.exec(response.headers["content-disposition"] || "")?.[1] ||
    `payroll_${params.period_start || "period"}.csv`;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
