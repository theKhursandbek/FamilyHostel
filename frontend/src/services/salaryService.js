import api from "./api";

export async function getSalaries(params = {}) {
  const response = await api.get("/salary/", { params });
  return response.data;
}
