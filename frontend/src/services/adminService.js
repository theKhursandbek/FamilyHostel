import api from "./api";

// ==================== CASH SESSIONS ====================

export async function getCashSessions(params = {}) {
  const response = await api.get("/admin-panel/cash-sessions/", { params });
  return response.data;
}

export async function getCashSession(id) {
  const response = await api.get(`/admin-panel/cash-sessions/${id}/`);
  return response.data;
}

export async function getCashSessionToday() {
  const response = await api.get("/admin-panel/cash-sessions/today/");
  return response.data;
}

export async function openCashSession(data) {
  const response = await api.post("/admin-panel/cash-sessions/open/", data);
  return response.data;
}

export async function closeCashSession(id, data) {
  const response = await api.post(`/admin-panel/cash-sessions/${id}/close/`, data);
  return response.data;
}

export async function handoverCashSession(id, data) {
  const response = await api.post(`/admin-panel/cash-sessions/${id}/handover/`, data);
  return response.data;
}

export async function reviewCashSession(id, data) {
  // data: { decision: "approved" | "disputed", comment?: string }
  const response = await api.post(`/admin-panel/cash-sessions/${id}/review/`, data);
  return response.data;
}

// ==================== ROOMS (for inspection dropdown) ====================

export async function getRooms(params = {}) {
  const response = await api.get("/branches/rooms/", { params });
  return response.data;
}

// ==================== ACCOUNTS (for handover dropdown) ====================

export async function getAccounts(params = {}) {
  const response = await api.get("/auth/accounts/", { params });
  return response.data;
}
