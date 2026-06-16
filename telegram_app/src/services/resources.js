import api from "./api";

/**
 * Read-only catalogue endpoints used by the public/client UI.
 *
 * NOTE (Phase 0 / TELEGRAM_MINI_APP_PLAN.md): kept as a thin shim so the
 * surviving HomePage / RoomDetailPage / BookingFlowPage still compile.
 * Phase 3 replaces this module with `services/catalogue.js` (cursor-paginated
 * room list, branch enum lookup, etc.).
 */

export async function listBranches() {
  const r = await api.get("/branches/");
  return r.data?.results ?? r.data ?? [];
}

export async function getRoom(id) {
  const r = await api.get(`/rooms/${id}/`);
  return r.data;
}
