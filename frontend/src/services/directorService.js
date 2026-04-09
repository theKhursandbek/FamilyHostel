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

// ==================== FACILITY LOGS ====================

export async function getFacilityLogs(params = {}) {
  const response = await api.get("/facility-logs/", { params });
  return response.data;
}

export async function createFacilityLog(data) {
  const response = await api.post("/facility-logs/", data);
  return response.data;
}

export async function updateFacilityLog(id, data) {
  const response = await api.patch(`/facility-logs/${id}/`, data);
  return response.data;
}

// ==================== ACCOUNTS (for penalty/assignment dropdowns) ====================

export async function getAccounts(params = {}) {
  const response = await api.get("/auth/accounts/", { params });
  return response.data;
}
