import api, { unwrap } from "./api";
import { hasToken } from "./auth";

/**
 * Booking-related API calls. The backend exposes a single
 * `/bookings/bookings/` viewset; clients can list & create their own
 * bookings, and cancel pending ones.
 *
 * Guest mode (no login): we look bookings up by phone via the
 * /payments/guest/bookings/ endpoints.
 */

const GUEST_PHONE_KEY = "guest_phone";

export function rememberGuestPhone(phone) {
  if (phone) localStorage.setItem(GUEST_PHONE_KEY, phone);
}

export function getGuestPhone() {
  return localStorage.getItem(GUEST_PHONE_KEY) || "";
}

export function clearGuestPhone() {
  localStorage.removeItem(GUEST_PHONE_KEY);
}

/**
 * Fire a global event so any mounted bookings list re-fetches itself.
 * Called after a booking is created or paid.
 */
export function notifyBookingsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("bookings:changed"));
  }
}

export async function getAvailability(roomId, fromDate, toDate) {
  const r = await api.get("/bookings/availability/", {
    params: { room: roomId, from: fromDate, to: toDate },
  });
  return unwrap(r) ?? { available: true, blocked_dates: [] };
}

export async function listMyBookings() {
  // /bookings/my/ is the client-only endpoint (IsAuthenticated). It returns
  // every booking owned by the caller — no admin-scope filter so the past
  // tab keeps full history.
  const r = await api.get("/bookings/my/");
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}

export async function listGuestBookings(phone) {
  const p = phone || getGuestPhone();
  if (!p) return [];
  const r = await api.get("/payments/guest/bookings/", { params: { phone: p } });
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}

export async function getBooking(id) {
  const r = await api.get(`/bookings/my/${id}/`);
  return unwrap(r);
}

export async function getGuestBooking(id, phone) {
  const p = phone || getGuestPhone();
  const r = await api.get(`/payments/guest/bookings/${id}/`, { params: { phone: p } });
  return unwrap(r);
}

export async function createBooking({
  room,
  branch,
  check_in_date,
  check_out_date,
  price_at_booking,
  discount_amount = 0,
}) {
  const r = await api.post("/bookings/bookings/", {
    room,
    branch,
    check_in_date,
    check_out_date,
    price_at_booking,
    discount_amount,
  });
  return unwrap(r);
}

export async function cancelBooking(id) {
  // Guest mode: route via the guest endpoint with the remembered phone.
  const phone = getGuestPhone();
  if (!hasToken() && phone) {
    const r = await api.post(
      `/payments/guest/bookings/${id}/cancel/`,
      null,
      { params: { phone } },
    );
    return unwrap(r);
  }
  const r = await api.post(`/bookings/my/${id}/cancel/`);
  return unwrap(r);
}
