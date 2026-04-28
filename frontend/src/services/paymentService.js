import api from "./api";

/**
 * Record a payment against a booking.
 * Backend (apps/payments/services.py) will:
 *   - create the Payment row
 *   - mark booking.status = "paid"
 *   - emit payment_completed websocket event
 *
 * @param {{ booking: number, amount: number|string, payment_type?: "manual"|"online", method?: "cash"|"terminal"|"qr"|"card_transfer" }} payload
 */
export async function recordPayment({ booking, amount, payment_type = "manual", method = "cash" }) {
  const { data } = await api.post("/payments/payments/", {
    booking,
    amount,
    payment_type,
    method,
  });
  return data;
}

/** List all payments belonging to a booking. */
export async function getBookingPayments(bookingId) {
  const { data } = await api.get("/payments/payments/", {
    params: { booking: bookingId },
  });
  return data.results ?? data;
}
