import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getBooking } from "../../services/bookings";
import { createIntentForExtension } from "../../services/payments";
import useMainButton from "../../hooks/useMainButton";
import { describeDraftError } from "../../utils/draftErrors";
import BackButton from "../../components/BackButton";
import { validateDateRange } from "../../utils/validators";

/**
 * Extend an existing paid booking — Telegram Mini App, Phase 7.
 *
 * Client picks a new check-out date later than the current one. We POST
 * /payments/draft/extension/ to create an :class:`ExtensionDraft` and a
 * Stripe PaymentIntent, then route to the shared payment screen.
 */
export default function ExtendFlowPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [newDate, setNewDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    let alive = true;
    getBooking(id)
      .then((b) => {
        if (!alive) return;
        setBooking(b);
        // Leave newDate empty — user must explicitly pick a later checkout
        // before the Pay button is enabled.
      })
      .catch((e) => alive && setError(e?.message || "load_failed"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [id]);

  const minDate = useMemo(() => {
    if (!booking) return undefined;
    const next = new Date(booking.check_out_date);
    next.setDate(next.getDate() + 1);
    return next.toISOString().slice(0, 10);
  }, [booking]);

  const extraNights = useMemo(() => {
    if (!booking || !newDate) return 0;
    const a = new Date(booking.check_out_date);
    const b = new Date(newDate);
    return Math.max(0, Math.round((b - a) / 86_400_000));
  }, [booking, newDate]);

  const dateCheck = useMemo(() => {
    if (!booking || !newDate) return { ok: false, code: "required", messageKey: "validation.required" };
    return validateDateRange(booking.check_out_date, newDate, {
      minNights: 1,
      maxNights: 365,
      allowStartInPast: true,
    });
  }, [booking, newDate]);
  const dateError = newDate && !dateCheck.ok ? dateCheck : null;

  const total = useMemo(() => {
    if (!booking || !extraNights) return 0;
    return Number(booking.price_at_booking || 0) / Math.max(
      1,
      Math.round(
        (new Date(booking.check_out_date) - new Date(booking.check_in_date))
          / 86_400_000,
      ),
    ) * extraNights;
  }, [booking, extraNights]);

  const canSubmit = booking
    && booking.status === "paid"
    && dateCheck.ok
    && extraNights >= 1
    && !submitting;

  const handleConfirm = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const draft = await createIntentForExtension({
        booking: Number(id),
        new_check_out_date: newDate,
      });
      navigate(`/pay/${draft.draft_id}`, { state: { draft } });
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

  if (loading) return <div className="page-loading">{t("common.loading")}</div>;
  if (error || !booking) return <div className="page-error">{t("common.load_failed")}</div>;
  if (booking.status !== "paid") {
    return (
      <div className="page-error">
        <p>{t("extend.only_paid")}</p>
        <button type="button" className="btn btn-primary" onClick={() => navigate(-1)}>
          {t("common.back")}
        </button>
      </div>
    );
  }

  const fmt = (n) => new Intl.NumberFormat(i18n.language).format(Math.round(n));

  return (
    <section className="booking-flow">
      <BackButton />
      <header className="booking-flow__header">
        <h1>{t("extend.title")}</h1>
        <p className="muted">
          {t("my_bookings.booking_no", { id: booking.id })} · {booking.branch_name}
        </p>
      </header>

      <div className="booking-flow__dates" style={{ gridTemplateColumns: "1fr" }}>
        <label>
          <span>{t("extend.current_check_out")}</span>
          <input type="date" value={booking.check_out_date} disabled readOnly />
        </label>
        <label>
          <span>{t("extend.new_check_out")}</span>
          <input
            type="date"
            min={minDate}
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
          />
          {dateError && (
            <small className="form-hint form-hint--error">
              {t(dateError.messageKey, dateError.code, dateError.params)}
            </small>
          )}
        </label>
      </div>

      <div className="booking-flow__summary">
        <div className="row">
          <span>{t("extend.extra_nights", "Qo‘shimcha kun")}</span>
          <strong>{t("booking.days_count", { count: extraNights, defaultValue: "{{count}} kun" })}</strong>
        </div>
        <div className="row total">
          <span>{t("booking.total")}</span>
          <strong>{fmt(total)} UZS</strong>
        </div>
      </div>

      {submitError && <div className="form-error" role="alert">{submitError}</div>}

      {/* Fallback CTA for browsers without Telegram MainButton. */}
      <button
        type="button"
        className="btn btn-primary"
        style={{ width: "100%", marginTop: 16 }}
        onClick={handleConfirm}
        disabled={!canSubmit}
      >
        {submitting
          ? t("booking.creating", "…")
          : t("booking.pay", "Pay")}
      </button>

      <p className="legal-note">{t("booking.no_refund_notice")}</p>
    </section>
  );
}
