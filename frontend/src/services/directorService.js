import api from "./api";

// ==================== DAYS OFF APPROVAL ====================

export async function getAllDayOffRequests(params = {}) {
  const response = await api.get("/staff/day-off-requests/", { params });
  return response.data;
}

export async function approveDayOff(id, comment = "") {
  const response = await api.post(`/staff/day-off-requests/${id}/approve/`, { comment });
  return response.data;
}

export async function rejectDayOff(id, comment = "") {
  const response = await api.post(`/staff/day-off-requests/${id}/reject/`, { comment });
  return response.data;
}

// ==================== PENALTIES ====================

export async function getPenalties(params = {}) {
  const response = await api.get("/penalties/", { params });
  return response.data;
}

export async function createPenalty(data) {
  const response = await api.post("/penalties/", data);
  return response.data;
}

export async function deletePenalty(id) {
  const response = await api.delete(`/penalties/${id}/`);
  return response.data;
}

// ==================== FACILITY LOGS / EXPENSE REQUESTS ====================
// REFACTOR_PLAN_2026_04 §7. The endpoint is still /facility-logs/ but the
// lifecycle is: pending → approved_cash|approved_card → paid → resolved.

export async function getFacilityLogs(params = {}) {
  const response = await api.get("/facility-logs/", { params });
  return response.data;
}

export async function createFacilityLog(data) {
  // POST → status='pending'. Director files an expense request.
  const response = await api.post("/facility-logs/", data);
  return response.data;
}

export async function updateFacilityLog(id, data) {
  const response = await api.patch(`/facility-logs/${id}/`, data);
  return response.data;
}

export async function approveExpenseRequest(id, payload) {
  // payload: {payment_method:'cash'|'card', note?, over_limit_justified?, over_limit_reason?}
  const response = await api.post(`/facility-logs/${id}/approve/`, payload);
  return response.data;
}

export async function rejectExpenseRequest(id, reason) {
  const response = await api.post(`/facility-logs/${id}/reject/`, { reason });
  return response.data;
}

export async function markExpensePaid(id) {
  const response = await api.post(`/facility-logs/${id}/mark-paid/`);
  return response.data;
}

export async function markExpenseResolved(id) {
  const response = await api.post(`/facility-logs/${id}/mark-resolved/`);
  return response.data;
}

// ==================== ACCOUNTS (for penalty/assignment dropdowns) ====================

export async function getAccounts(params = {}) {
  const response = await api.get("/auth/accounts/", { params });
  return response.data;
}
