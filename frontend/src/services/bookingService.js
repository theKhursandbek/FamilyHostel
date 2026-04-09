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
 * Cancel a pending booking.
 * POST /api/v1/bookings/bookings/{id}/cancel/
 */
export async function cancelBooking(id) {
  const response = await api.post(`/bookings/bookings/${id}/cancel/`);
  return response.data;
}

/**
 * Complete a paid booking.
 * POST /api/v1/bookings/bookings/{id}/complete/
 */
export async function completeBooking(id) {
  const response = await api.post(`/bookings/bookings/${id}/complete/`);
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
