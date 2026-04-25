import api, { unwrap } from "./api";

/* ---------- Public (no auth) ---------- */

export async function listBranches() {
  const r = await api.get("/public/branches/");
  return unwrap(r) ?? [];
}
export async function getBranch(id) {
  const r = await api.get(`/public/branches/${id}/`);
  return unwrap(r);
}
export async function listRoomsByBranch(branchId) {
  const r = await api.get("/public/rooms/", { params: { branch: branchId } });
  return unwrap(r) ?? [];
}
export async function getRoom(id) {
  const r = await api.get(`/public/rooms/${id}/`);
  return unwrap(r);
}

/* ---------- Authenticated ---------- */

export async function listMyBookings() {
  // The backend bookings filter understands `mine=true` for the requesting
  // client; if not, the response will simply be an empty list.
  const r = await api.get("/bookings/bookings/", { params: { mine: "true" } });
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}

export async function listMyTasks() {
  const r = await api.get("/cleaning/tasks/", { params: { mine: "true" } });
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}

export async function listMyDaysOff() {
  const r = await api.get("/staff/days-off/");
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}

export async function listMyPenalties() {
  const r = await api.get("/penalties/", { params: { mine: "true" } });
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}
