/**
 * Map a backend draft-creation error code to a user-facing i18n key.
 *
 * Backend emits ``{code, detail}`` from :class:`apps.payments.draft_service.DraftError`.
 * Anything we don't recognise falls through so the raw detail is shown.
 *
 * @param {object} err  Axios error (or a plain object with response.data).
 * @param {(key: string, fallback?: string) => string} t  i18next ``t`` function.
 * @returns {string}    A localised, user-friendly message.
 */
export function describeDraftError(err, t) {
  const data = err?.response?.data || err?.data || {};
  const code = data.code || data?.error?.code;
  const fallback = (typeof data.detail === "string" && data.detail)
    || err?.message
    || t("common.error", "Something went wrong.");

  switch (code) {
    case "overlap_with_existing_booking":
      return t(
        "booking.error_overlap",
        "These dates were just booked. Please pick another room or different dates.",
      );
    case "room_held_by_other_user":
      return t(
        "booking.error_held",
        "Someone else is currently checking out this room. Try again in a few minutes or pick another room.",
      );
    case "room_not_available":
      return t("booking.error_room_unavailable", "This room is not available right now.");
    case "check_in_in_past":
      return t("booking.error_past", "Check-in date is in the past.");
    case "range_too_short":
      return t("booking.error_short", "Pick at least one full night.");
    case "range_too_long":
      return t("booking.error_long", "That stay is too long.");
    case "check_in_too_far":
      return t("booking.error_too_far", "Check-in date is too far in the future.");
    case "booking_not_active":
      return t("booking.error_not_active", "Only paid bookings can be modified.");
    default:
      return fallback;
  }
}
