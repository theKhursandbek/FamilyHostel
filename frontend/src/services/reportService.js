import api from "./api";

export async function getAvailableWorkbooks() {
  const { data } = await api.get("/reports/workbook/available/");
  return data?.results ?? [];
}

export async function downloadBranchWorkbook(branchId, year) {
  const response = await api.get(
    `/reports/workbook/branch/${branchId}/${year}/`,
    { responseType: "blob" },
  );
  return response;
}

export async function downloadGeneralManagerWorkbook(directorId, year) {
  const response = await api.get(
    `/reports/workbook/general-manager/${directorId}/${year}/`,
    { responseType: "blob" },
  );
  return response;
}

/**
 * GET /reports/branch-dashboard/?branch=&year=&month=
 * In-page report payload — KPIs, income matrix, expenses, penalties,
 * salary roster, cash sessions. Identical coverage to the workbook.
 */
export async function getBranchDashboard({ branchId, year, month }) {
  const params = { branch: branchId };
  if (year) params.year = year;
  if (month) params.month = month;
  const { data } = await api.get("/reports/branch-dashboard/", { params });
  return data;
}

export async function getSalaryAdjustments({ branchId, year, month, kind, account } = {}) {
  const params = {};
  if (branchId) params.branch = branchId;
  if (year) params.year = year;
  if (month) params.month = month;
  if (kind) params.kind = kind;
  if (account) params.account = account;
  const { data } = await api.get("/reports/salary-adjustments/", { params });
  return data?.results ?? data;
}

export async function createSalaryAdjustment(payload) {
  // payload: {account, branch?, year, month, kind, amount, reason}
  const { data } = await api.post("/reports/salary-adjustments/", payload);
  return data;
}

export async function deleteSalaryAdjustment(id) {
  await api.delete(`/reports/salary-adjustments/${id}/`);
}

export async function getSalaryAdjustmentTargets({ branchId } = {}) {
  const params = {};
  if (branchId) params.branch = branchId;
  const { data } = await api.get(
    "/reports/salary-adjustments/targets/", { params },
  );
  return data?.results ?? [];
}

export async function getBranches(params = {}) {
  const response = await api.get("/branches/", { params });
  return response.data;
}

/**
 * Trigger a browser download from a Blob response (axios response object).
 */
export function saveBlob(response, fallbackName) {
  const cd = response.headers?.["content-disposition"] || "";
  const match = /filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i.exec(cd);
  const filename = match ? decodeURIComponent(match[1]) : fallbackName;
  const blob = new Blob([response.data], {
    type:
      response.headers?.["content-type"] ||
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = globalThis.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  globalThis.URL.revokeObjectURL(url);
}
