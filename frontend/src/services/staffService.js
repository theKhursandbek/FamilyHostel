import api from "./api";

// ==================== ATTENDANCE ====================

/**
 * Today's shift + check-in state for the logged-in user, flattened for the
 * dashboard chip. Reuses the existing GET /staff/me/today/ endpoint.
 */
export async function getTodayAttendance() {
  const { data } = await api.get("/staff/me/today/");
  const shift = data.shift || null;
  const att = data.attendance || null;
  return {
    date: data.today,
    shift_type: att?.shift_type || shift?.shift_type || null,
    branch: att?.branch ?? shift?.branch ?? null,
    checked_in: Boolean(att?.check_in),
    checked_in_at: att?.check_in || null,
    checked_out_at: att?.check_out || null,
    status: att?.check_in ? att.status : null,
  };
}

/** Record a check-in for the given branch/date/shift. */
export async function checkIn({ branch, date, shift_type }) {
  const response = await api.post("/staff/attendance/check-in/", {
    branch,
    date,
    shift_type,
  });
  return response.data;
}

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
