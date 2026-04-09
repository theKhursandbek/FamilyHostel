import api from "./api";

/**
 * Fetch admin dashboard data.
 * GET /api/v1/dashboard/admin/
 */
export async function getAdminDashboard() {
  const response = await api.get("/dashboard/admin/");
  return response.data;
}

/**
 * Fetch director dashboard data.
 * GET /api/v1/dashboard/director/
 */
export async function getDirectorDashboard() {
  const response = await api.get("/dashboard/director/");
  return response.data;
}

/**
 * Fetch super admin dashboard data.
 * GET /api/v1/dashboard/super-admin/
 */
export async function getSuperAdminDashboard() {
  const response = await api.get("/dashboard/super-admin/");
  return response.data;
}
