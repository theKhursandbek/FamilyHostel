import api from "./api";

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
 * Assign task (self-assign or director assign).
 * POST /api/v1/cleaning/tasks/{id}/assign/
 */
export async function assignTask(id, staffId = null) {
  const body = staffId ? { assigned_to: staffId } : {};
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
 * Director override — force-approve a task.
 * POST /api/v1/cleaning/tasks/{id}/override/
 */
export async function overrideTask(id, reason) {
  const response = await api.post(`/cleaning/tasks/${id}/override/`, { reason });
  return response.data;
}
