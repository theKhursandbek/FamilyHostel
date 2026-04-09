import api from "./api";

/**
 * Fetch admin dashboard data.
 * GET /api/v1/dashboard/admin/
 */
export async function getAdminDashboard() {
  const response = await api.get("/dashboard/admin/");
  return response.data;
}
