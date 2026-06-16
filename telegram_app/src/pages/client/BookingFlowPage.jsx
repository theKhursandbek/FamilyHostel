import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getRoom } from "../../services/catalogue";
import { createIntentForRoom } from "../../services/payments";
import { notifyBookingsChanged } from "../../services/bookings";
import { useAuth } from "../../context/AuthContext";
import useMainButton from "../../hooks/useMainButton";
import { describeDraftError } from "../../utils/draftErrors";
import PaymentCountdown from "../../components/PaymentCountdown";
import BackButton from "../../components/BackButton";
import { validateDateRange } from "../../utils/validators";

// Client-side reservation hold shown on this page. The real server-side
// hold is created when the user clicks Pay (BookingDraft.expires_at).
const RESERVATION_MS = 5 * 60 * 1000;

/**
 * Booking flow — Telegram Mini App, Phase 5.
 *
 * Steps:
 *   1. Pick check-in / check-out dates (+ guest details if not signed in).
 *   2. Confirm — server-side: create BookingDraft + Stripe PaymentIntent.
 *   3. Navigate to /pay/<draftId> with payment-intent metadata in router state.
 *
 * No Booking row exists at this stage (D5).
 */
export default function BookingFlowPage() {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();

  const [room, setRoom] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Use the user's LOCAL calendar date — `toISOString()` returns UTC, which
  // shifts by one day for users east of UTC during early-morning hours and
  // causes the backend to reject `check_in_date` as `check_in_in_past`.
  const localDateStr = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };
  // Add `n` days to a YYYY-MM-DD string using LOCAL calendar arithmetic.
  const addDaysISO = (iso, n) => {
    const [y, m, d] = iso.split("-").map(Number);
    return localDateStr(new Date(y, m - 1, d + n));
  };
  const today = localDateStr(new Date());
  const tomorrow = localDateStr(new Date(Date.now() + 86_400_000));
  const [checkIn, setCheckIn] = useState(today);
  const [checkOut, setCheckOut] = useState(tomorrow);

  // Earliest valid check-out is the day AFTER check-in — same-day stays
  // are not allowed, so we constrain the native date picker via `min`
  // rather than relying on an inline error.
  const minCheckOut = useMemo(() => addDaysISO(checkIn, 1), [checkIn]);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // 5-minute reservation hold for this page. On expiry the user is sent
  // back to the home page — they need to start the booking flow over.
  const [deadline] = useState(() => Date.now() + RESERVATION_MS);
  const handleExpire = () => navigate("/", { replace: true });

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getRoom(roomId)
      .then((r) => { if (alive) setRoom(r); })
      .catch((e) => { if (alive) setError(e?.message || "load_failed"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [roomId]);

  const nights = useMemo(() => {
    const a = new Date(checkIn);
    const b = new Date(checkOut);
    const diff = Math.round((b - a) / 86_400_000);
    return diff > 0 ? diff : 0;
  }, [checkIn, checkOut]);

  const total = useMemo(() => {
    if (!room || !nights) return 0;
    return Number(room.base_price) * nights;
  }, [room, nights]);

  const dateCheck = useMemo(
    () => validateDateRange(checkIn, checkOut, { minNights: 1, maxNights: 365, allowStartInPast: false }),
    [checkIn, checkOut],
  );
  const dateError = !dateCheck.ok ? dateCheck : null;
  const datesValid = dateCheck.ok;
  const canSubmit = datesValid && !submitting && room && !loading;

  const handleConfirm = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const draft = await createIntentForRoom({
        room: Number(roomId),
        check_in_date: checkIn,
        check_out_date: checkOut,
      });
      notifyBookingsChanged();
      navigate(`/pay/${draft.draft_id}`, { state: { draft, room } });
    } catch (e) {
      setSubmitError(describeDraftError(e, t));
      setSubmitting(false);
    }
  };

  useMainButton({
    text: submitting ? t("booking.creating") : t("booking.pay", "Pay"),
    visible: !loading,
    disabled: !canSubmit,
    loading: submitting,
    onClick: handleConfirm,
  });

  if (loading) {
    return <div className="page-loading">{t("common.loading")}</div>;
  }
  if (error || !room) {
    return <div className="page-error">{t("common.load_failed")}</div>;
  }

  const fmt = (n) => new Intl.NumberFormat(i18n.language).format(n);
  const guestName =
    user?.full_name ||
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    "";

  return (
    <section className="booking-flow">
      <BackButton />
      <div className="booking-flow__timer" aria-label={t("payment.hold_remaining", "Reserved for")}>
        <PaymentCountdown
          expiresAt={deadline}
          onExpire={handleExpire}
          variant="compact"
        />
      </div>
      <header className="booking-flow__header">
        <h1>{t("booking.title")}</h1>
        <p className="muted">
          {room.branch_name} · {t("room.room_number", { n: room.room_number })}
        </p>
      </header>

      {/* Profile recap — no editable fields, profile is the source of truth. */}
      {guestName && (
        <div className="booking-flow__profile">
          <span className="muted">{t("booking.guest", "Guest")}:</span>{" "}
          <strong>{guestName}</strong>
          {user?.phone && (
            <>
              <span className="booking-flow__profile-sep"> · </span>
              <span>{user.phone}</span>
            </>
          )}
        </div>
      )}

      <div className="booking-flow__dates">
        <label>
          <span>{t("booking.check_in")}</span>
          <input
            type="date"
            min={today}
            value={checkIn}
            onChange={(e) => {
              const newIn = e.target.value;
              setCheckIn(newIn);
              // Auto-bump check-out so it stays strictly AFTER check-in.
              if (newIn && checkOut <= newIn) {
                setCheckOut(addDaysISO(newIn, 1));
              }
            }}
          />
        </label>
        <label>
          <span>{t("booking.check_out")}</span>
          <input
            type="date"
            min={minCheckOut}
            value={checkOut}
            onChange={(e) => setCheckOut(e.target.value)}
          />
        </label>
      </div>

      {dateError && (
        <small className="form-hint form-hint--error" style={{ display: "block", marginTop: 4 }}>
          {t(dateError.messageKey, dateError.code, dateError.params)}
        </small>
      )}

      <div className="booking-flow__summary">
        <div className="row">
          <span>{t("booking.nights")}</span>
          <strong>{t("booking.days_count", { count: nights, defaultValue: "{{count}} kun" })}</strong>
        </div>
        <div className="row">
          <span>{t("booking.price_per_night")}</span>
          <strong>{fmt(room.base_price)} UZS</strong>
        </div>
        <div className="row total">
          <span>{t("booking.total")}</span>
          <strong>{fmt(total)} UZS</strong>
        </div>
      </div>

      {/* Fallback CTA for desktop / browsers without Telegram MainButton. */}
      <button
        type="button"
        className="btn btn-primary"
        style={{ width: "100%", marginTop: 16 }}
        onClick={handleConfirm}
        disabled={!canSubmit}
      >
        {submitting
          ? t("booking.creating", "Yaratilmoqda…")
          : t("booking.pay", "Pay")}
      </button>

      {submitError && (
        <div className="form-error" role="alert">{submitError}</div>
      )}

      <p className="legal-note">{t("booking.no_refund_notice")}</p>
    </section>
  );
}
