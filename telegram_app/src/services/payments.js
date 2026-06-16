import api, { unwrap } from "./api";

/**
 * Payment endpoints — Telegram Mini App, Phase 5.
 *
 *  Mini App flow (D5 — clients pay first; the webhook converts the draft
 *  into a real Booking only on ``payment_intent.succeeded``):
 *      POST /payments/draft/room/         — create a BookingDraft
 *      POST /payments/draft/extension/    — create an ExtensionDraft
 *      GET  /payments/drafts/<uuid>/      — poll draft status
 *
 *  Legacy admin-issued flow (kept for compatibility):
 *      POST /payments/stripe/intent/      — intent for an existing Booking
 *      GET  /payments/payments/?booking=  — list payments for a booking
 */

// Mini App — payment-first drafts ------------------------------------------

export async function createIntentForRoom({
  room,
  check_in_date,
  check_out_date,
  full_name,
  phone,
}) {
  const r = await api.post("/payments/draft/room/", {
    room,
    check_in_date,
    check_out_date,
    // Guest checkout — backend treats these as required when caller is anonymous.
    ...(full_name ? { full_name } : {}),
    ...(phone ? { phone } : {}),
  });
  return unwrap(r);
}

export async function createIntentForExtension({ booking, new_check_out_date }) {
  const r = await api.post("/payments/draft/extension/", {
    booking,
    new_check_out_date,
  });
  return unwrap(r);
}

export async function getDraft(draftId) {
  const r = await api.get(`/payments/drafts/${draftId}/`);
  return unwrap(r);
}

export async function demoConfirmDraft(draftId) {
  const r = await api.post(`/payments/drafts/${draftId}/demo-confirm/`);
  return unwrap(r);
}

/**
 * Poll until draft status leaves ``pending`` or the timeout window elapses.
 * Returns the final draft payload (possibly still ``pending``).
 */
export async function pollDraftUntilSettled(draftId, {
  intervalMs = 1500,
  timeoutMs = 30_000,
} = {}) {
  const started = Date.now();
  let last = null;
  while (Date.now() - started < timeoutMs) {
    last = await getDraft(draftId);
    if (last && last.status !== "pending") {
      return last;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return last ?? { status: "pending", booking_id: null };
}

// Legacy --------------------------------------------------------------------

export async function createStripeIntent(bookingId) {
  const r = await api.post("/payments/stripe/intent/", { booking: bookingId });
  return unwrap(r);
}

export async function listBookingPayments(bookingId) {
  const r = await api.get("/payments/payments/", { params: { booking: bookingId } });
  const data = unwrap(r);
  return data?.results ?? data ?? [];
}
