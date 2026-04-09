import api from "./api";

export async function getReports(params = {}) {
  const response = await api.get("/reports/", { params });
  return response.data;
}

export async function exportCSV(params = {}) {
  const response = await api.get("/reports/export/", {
    params,
    responseType: "blob",
  });
  return response;
}

export async function getBranches(params = {}) {
  const response = await api.get("/branches/", { params });
  return response.data;
}
