import api from "./api";

// ==================== DAY-OFF REQUESTS ====================

export async function getDayOffRequests(params = {}) {
  const response = await api.get("/staff/day-off-requests/", { params });
  return response.data;
}

export async function createDayOffRequest(data) {
  const response = await api.post("/staff/day-off-requests/", data);
  return response.data;
}

// ==================== PENALTIES (own view) ====================

export async function getMyPenalties(params = {}) {
  const response = await api.get("/penalties/", { params });
  return response.data;
}
