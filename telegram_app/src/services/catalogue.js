/**
 * Catalogue services — Telegram Mini App, Phase 3.
 *
 * Public read-only endpoints exposed by `apps/branches/public_urls.py`.
 * The catalogue list uses **cursor pagination** (D17): callers pass the
 * absolute `next` URL returned by the previous page back into `listRooms`.
 */
import api, { unwrap } from "./api";

const BASE = "/public";

/**
 * Build the query string the catalogue endpoint expects.
 * Drops empty values to keep the URL clean.
 */
function buildParams(filters = {}) {
  const out = {};
  if (filters.priceMin !== undefined && filters.priceMin !== "" && filters.priceMin !== null) {
    out.price_min = String(filters.priceMin);
  }
  if (filters.priceMax !== undefined && filters.priceMax !== "" && filters.priceMax !== null) {
    out.price_max = String(filters.priceMax);
  }
  if (Array.isArray(filters.roomTypeIds) && filters.roomTypeIds.length) {
    out.room_type = filters.roomTypeIds.join(",");
  }
  if (Array.isArray(filters.locations) && filters.locations.length) {
    out.location = filters.locations.join(",");
  }
  if (filters.available === false) {
    out.available = "false";
  }
  if (filters.pageSize) {
    out.page_size = String(filters.pageSize);
  }
  return out;
}

/**
 * Fetch one page of the catalogue.
 *
 * @param {object}        opts
 * @param {object}        [opts.filters] — UI filter state.
 * @param {string|null}   [opts.cursorUrl] — the absolute `next` URL from the
 *                                            previous page; when set, every
 *                                            other parameter is ignored
 *                                            because the cursor already
 *                                            encodes them.
 * @returns {Promise<{ results: Array, next: string|null, previous: string|null }>}
 */
export async function listRooms({ filters = {}, cursorUrl = null } = {}) {
  if (cursorUrl) {
    const r = await api.get(cursorUrl);
    return unwrap(r) ?? r.data;
  }
  const r = await api.get(`${BASE}/rooms/`, { params: buildParams(filters) });
  return unwrap(r) ?? r.data;
}

export async function getRoom(id) {
  const r = await api.get(`${BASE}/rooms/${id}/`);
  return unwrap(r) ?? r.data;
}

export async function listBranches() {
  const r = await api.get(`${BASE}/branches/`);
  const data = unwrap(r) ?? r.data;
  return Array.isArray(data) ? data : data?.results ?? [];
}

export async function listRoomTypes() {
  const r = await api.get(`${BASE}/room-types/`);
  const data = unwrap(r) ?? r.data;
  return Array.isArray(data) ? data : data?.results ?? [];
}

export async function listLocations() {
  const r = await api.get(`${BASE}/locations/`);
  const data = unwrap(r) ?? r.data;
  return Array.isArray(data) ? data : [];
}
