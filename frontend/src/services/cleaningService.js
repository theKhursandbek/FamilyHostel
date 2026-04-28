import api from "./api";
import { listAccounts } from "./accountsService";

/**
 * Fetch cleaning tasks list.
 * GET /api/v1/cleaning/tasks/
 */
export async function getTasks(params = {}) {
  const response = await api.get("/cleaning/tasks/", { params });
  return response.data;
}

/**
 * Fetch a single cleaning task detail.
 * GET /api/v1/cleaning/tasks/{id}/
 */
export async function getTask(id) {
  const response = await api.get(`/cleaning/tasks/${id}/`);
  return response.data;
}

/**
 * Create a new cleaning task (admin/director).
 * POST /api/v1/cleaning/tasks/
 *
 * @param {object} payload - { room, branch, priority, assigned_to? }
 *   - assigned_to is optional. If omitted, the task starts as "pending"
 *     so any staff member can pick it up themselves.
 */
export async function createTask(payload) {
  const response = await api.post("/cleaning/tasks/", payload);
  return response.data;
}

/**
 * Update a cleaning task (priority, assignee).
 * PATCH /api/v1/cleaning/tasks/{id}/
 */
export async function updateTask(id, payload) {
  const response = await api.patch(`/cleaning/tasks/${id}/`, payload);
  return response.data;
}

/**
 * Delete a cleaning task.
 * DELETE /api/v1/cleaning/tasks/{id}/
 */
export async function deleteTask(id) {
  const response = await api.delete(`/cleaning/tasks/${id}/`);
  return response.data;
}

/**
 * Assign task. Staff: self-assign (no body). Director+/Admin+: pass staffId.
 * POST /api/v1/cleaning/tasks/{id}/assign/
 */
export async function assignTask(id, staffId = null) {
  const body = staffId ? { staff_id: staffId } : {};
  const response = await api.post(`/cleaning/tasks/${id}/assign/`, body);
  return response.data;
}

/**
 * Complete a cleaning task.
 * POST /api/v1/cleaning/tasks/{id}/complete/
 */
export async function completeTask(id) {
  const response = await api.post(`/cleaning/tasks/${id}/complete/`);
  return response.data;
}

/**
 * Upload images for a cleaning task.
 * POST /api/v1/cleaning/tasks/{id}/upload/
 * Content-Type: multipart/form-data
 */
export async function uploadImages(id, files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("images", file);
  }
  const response = await api.post(`/cleaning/tasks/${id}/upload/`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

/**
 * Retry a cleaning task (retry_required → in_progress).
 * POST /api/v1/cleaning/tasks/{id}/retry/
 */
export async function retryTask(id) {
  const response = await api.post(`/cleaning/tasks/${id}/retry/`);
  return response.data;
}

/**
 * Manual override — admin / director / superadmin force-approve.
 * POST /api/v1/cleaning/tasks/{id}/override/
 */
export async function overrideTask(id, reason) {
  const response = await api.post(`/cleaning/tasks/${id}/override/`, { reason });
  return response.data;
}

/**
 * Lightweight staff list helper for assignment dropdowns.
 * Uses listAccounts() which targets /auth/accounts/ and unwraps the response.
 *
 * Pass `{ freeForCleaning: true }` to ask the backend to exclude any staff
 * who currently has an active (non-completed) cleaning task — so the
 * dropdown only shows people who can actually be assigned right now.
 *
 * Returns array of { staff_profile_id, full_name, branch_id, branch_name }.
 */
export async function listStaffForAssignment({ freeForCleaning = false } = {}) {
  const params = { role: "staff", is_active: true };
  if (freeForCleaning) params.free_for_cleaning = true;
  const list = await listAccounts(params);
  return (list ?? [])
    .filter((a) => a.staff_profile_id)
    .map((a) => ({
      staff_profile_id: a.staff_profile_id,
      full_name: a.full_name,
      branch_id: a.branch_id,
      branch_name: a.branch_name,
    }));
}
