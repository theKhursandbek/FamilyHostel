import api from "./api";

export async function getSalaries(params = {}) {
  const response = await api.get("/payments/salary/", { params });
  return response.data;
}
