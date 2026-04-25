import api from "./api";

export async function getShifts(params = {}) {
  const response = await api.get("/staff/shifts/", { params });
  return response.data;
}

export async function createShift(data) {
  const response = await api.post("/staff/shifts/", data);
  return response.data;
}

// ==================== HELPERS (accounts & branches) ====================

export async function getAccounts(params = {}) {
  const response = await api.get("/auth/accounts/", { params });
  return response.data;
}

export async function getBranches(params = {}) {
  const response = await api.get("/branches/", { params });
  return response.data;
}
