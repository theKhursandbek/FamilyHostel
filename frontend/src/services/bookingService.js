import api from "./api";

/**
 * Fetch bookings list.
 * GET /api/v1/bookings/bookings/
 */
export async function getBookings(params = {}) {
  const response = await api.get("/bookings/bookings/", { params });
  return response.data;
}

/**
 * Fetch a single booking.
 * GET /api/v1/bookings/bookings/{id}/
 */
export async function getBooking(id) {
  const response = await api.get(`/bookings/bookings/${id}/`);
  return response.data;
}

/**
 * Create a new booking.
 * POST /api/v1/bookings/bookings/
 */
export async function createBooking(data) {
  const response = await api.post("/bookings/bookings/", data);
  return response.data;
}

/**
 * Create a walk-in booking.
 * POST /api/v1/bookings/bookings/walk-in/
 */
export async function createWalkInBooking(data) {
  const response = await api.post("/bookings/bookings/walk-in/", data);
  return response.data;
}

/**
 * Create a 5-minute room hold (Telegram Mini App flow).
 * POST /api/v1/payments/draft/room/
 */
export async function createBookingHold(data) {
  const response = await api.post("/payments/draft/room/", data);
  return response.data;
}

/**
 * Extend an existing booking by pushing the check-out date later.
 * POST /api/v1/bookings/bookings/{id}/extend/
 *
 * Payload: { new_check_out_date, additional_price }
 */
export async function extendBooking(id, data) {
  const response = await api.post(`/bookings/bookings/${id}/extend/`, data);
  return response.data;
}

/**
 * Cancel a pending booking.
 * POST /api/v1/bookings/bookings/{id}/cancel/
 */
export async function cancelBooking(id) {
  const response = await api.post(`/bookings/bookings/${id}/cancel/`);
  return response.data;
}

/**
 * Cancel only the latest active extension on a booking (Scenario A) — the
 * base stay survives. No refund is issued.
 * POST /api/v1/bookings/bookings/{id}/cancel-extension/
 */
export async function cancelExtension(id) {
  const response = await api.post(`/bookings/bookings/${id}/cancel-extension/`);
  return response.data;
}

/**
 * Fetch the occupied date windows for a room so the UI can block overlapping
 * selections.
 * GET /api/v1/bookings/bookings/availability/?room=<id>[&exclude=<pk>][&after=<date>]
 *
 * @param {number|string} roomId
 * @param {{ exclude?: number|string, after?: string }} [opts]
 * @returns {Promise<{ room: number, booked_ranges: Array, next_booking_start?: string|null }>}
 */
export async function getAvailability(roomId, { exclude, after } = {}) {
  const params = { room: roomId };
  if (exclude != null) params.exclude = exclude;
  if (after) params.after = after;
  const response = await api.get("/bookings/bookings/availability/", { params });
  return response.data;
}

/**
 * Check the guest out of a paid booking.
 * POST /api/v1/bookings/bookings/{id}/checkout/
 *
 * Per April 2026 rule: early checkout does NOT refund the guest —
 * the unused nights are forfeit. For exceptional refunds use the
 * separate ``/refund/`` endpoint.
 */
export async function checkoutBooking(id) {
  const response = await api.post(`/bookings/bookings/${id}/checkout/`);
  return response.data;
}

/**
 * @deprecated Use {@link checkoutBooking} instead.
 */
export async function completeBooking(id) {
  return checkoutBooking(id);
}

/**
 * Issue a manual refund (negative-amount Payment row).
 * POST /api/v1/bookings/bookings/{id}/refund/
 *
 * @param {number} id
 * @param {{ amount: number|string, reason?: string }} payload
 */
export async function refundBooking(id, payload) {
  const response = await api.post(`/bookings/bookings/${id}/refund/`, payload);
  return response.data;
}

/**
 * Fetch rooms list (for booking form dropdown).
 * GET /api/v1/branches/rooms/
 */
export async function getRooms(params = {}) {
  const response = await api.get("/branches/rooms/", { params });
  return response.data;
}
