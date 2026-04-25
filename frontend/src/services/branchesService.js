import api from "./api";

/**
 * Branches & Rooms management API client (CEO).
 *
 * Backend endpoints are mounted under /api/v1/branches/.
 * The global axios interceptor strips the {success,data} envelope.
 */

const BRANCHES = "/branches/branches/";
const ROOM_TYPES = "/branches/room-types/";
const ROOMS = "/branches/rooms/";

function unwrapList(data) {
  return data?.results ?? data ?? [];
}

// Branches ------------------------------------------------------------------
export async function listBranches(params = {}) {
  const { data } = await api.get(BRANCHES, { params });
  return unwrapList(data);
}

/**
 * Build a payload that includes a hero image. When `imageFile` is a File the
 * request is sent as multipart/form-data so Django can save the upload.
 */
function buildBranchBody(payload, imageFile) {
  if (!imageFile) return { body: payload, isMultipart: false };
  const fd = new FormData();
  Object.entries(payload).forEach(([k, v]) => {
    if (v !== undefined && v !== null) fd.append(k, typeof v === "boolean" ? String(v) : v);
  });
  fd.append("image", imageFile);
  return { body: fd, isMultipart: true };
}

export async function createBranch(payload, imageFile = null) {
  const { body, isMultipart } = buildBranchBody(payload, imageFile);
  const { data } = await api.post(BRANCHES, body, isMultipart
    ? { headers: { "Content-Type": "multipart/form-data" } }
    : undefined);
  return data;
}

export async function updateBranch(id, payload, imageFile = null) {
  const { body, isMultipart } = buildBranchBody(payload, imageFile);
  const { data } = await api.patch(`${BRANCHES}${id}/`, body, isMultipart
    ? { headers: { "Content-Type": "multipart/form-data" } }
    : undefined);
  return data;
}

export async function deleteBranch(id) {
  await api.delete(`${BRANCHES}${id}/`);
}

// Room types ----------------------------------------------------------------
export async function listRoomTypes(params = {}) {
  const { data } = await api.get(ROOM_TYPES, { params });
  return unwrapList(data);
}

export async function createRoomType(payload) {
  const { data } = await api.post(ROOM_TYPES, payload);
  return data;
}

export async function updateRoomType(id, payload) {
  const { data } = await api.patch(`${ROOM_TYPES}${id}/`, payload);
  return data;
}

export async function deleteRoomType(id) {
  await api.delete(`${ROOM_TYPES}${id}/`);
}

// Rooms ---------------------------------------------------------------------
export async function listRooms(params = {}) {
  const { data } = await api.get(ROOMS, { params });
  return unwrapList(data);
}

export async function createRoom(payload) {
  const { data } = await api.post(ROOMS, payload);
  return data;
}

export async function updateRoom(id, payload) {
  const { data } = await api.patch(`${ROOMS}${id}/`, payload);
  return data;
}

export async function deleteRoom(id) {
  await api.delete(`${ROOMS}${id}/`);
}

// Room images (max 3 per room — backend enforced) ---------------------------
export const MAX_ROOM_IMAGES = 3;

export async function uploadRoomImages(roomId, files) {
  if (!files?.length) return [];
  const fd = new FormData();
  files.forEach((f) => fd.append("images", f));
  const { data } = await api.post(`${ROOMS}${roomId}/images/`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteRoomImage(roomId, imageId) {
  await api.delete(`${ROOMS}${roomId}/images/${imageId}/`);
}
