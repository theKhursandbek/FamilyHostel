import { useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";

import { demoConfirmDraft, getDraft, pollDraftUntilSettled } from "../../services/payments";
import { notifyBookingsChanged } from "../../services/bookings";
import { useAuth } from "../../context/AuthContext";
import useMainButton from "../../hooks/useMainButton";
import PaymentCountdown from "../../components/PaymentCountdown";
import BackButton from "../../components/BackButton";

/**
 * Stripe payment screen — Telegram Mini App, Phase 5.
 *
 * Receives the draft payload via router state (when arriving from
 * BookingFlowPage) and falls back to ``GET /payments/drafts/<id>/`` when the
 * page is opened directly (refresh / deep link).
 *
 * After ``stripe.confirmPayment`` resolves, we poll the draft for up to
 * 30 s; on ``succeeded`` → /me/bookings/<id>, on ``failed`` → inline retry.
 */
export default function PaymentPage() {
  const { draftId } = useParams();
  const { state } = useLocation();
  const { t } = useTranslation();

  const [draft, setDraft] = useState(state?.draft ?? null);
  const [loading, setLoading] = useState(!state?.draft);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (draft) return;
    let alive = true;
    getDraft(draftId)
      .then((d) => { if (alive) setDraft(d); })
      .catch((e) => { if (alive) setError(e?.message || "load_failed"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [draftId, draft]);

  const stripePromise = useMemo(() => {
    if (!draft?.publishable_key) return null;
    return loadStripe(draft.publishable_key);
  }, [draft?.publishable_key]);

  if (loading) return <div className="page-loading">{t("common.loading")}</div>;
  if (error || !draft) return <div className="page-error">{t("common.load_failed")}</div>;

  // Demo-pending (Stripe disabled in dev) — show countdown + fake Pay button.
  if (draft.intent_status === "demo_pending") {
    return <DemoPaymentForm draft={draft} draftId={draftId} setDraft={setDraft} />;
  }

  // Legacy fake-paid response (booking already created server-side).
  if (draft.intent_status === "fake_paid" && draft.booking_id) {
    return <SettledRedirect bookingId={draft.booking_id} />;
  }

  // If the draft already settled (e.g. a returning user), short-circuit.
  if (draft.status === "succeeded" && draft.booking_id) {
    return <SettledRedirect bookingId={draft.booking_id} />;
  }

  if (!draft.client_secret || !stripePromise) {
    return <div className="page-error">{t("common.load_failed")}</div>;
  }

  return (
    <Elements
      stripe={stripePromise}
      options={{
        clientSecret: draft.client_secret,
        appearance: {
          theme: "stripe",
          variables: {
            colorPrimary: "#b08d57",
            colorBackground: "#fdfbf6",
            colorText: "#1a2238",
            colorTextSecondary: "#6a6e7a",
            colorDanger: "#a13b3b",
            fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
            borderRadius: "12px",
          },
        },
      }}
    >
      <PaymentForm draft={draft} draftId={draftId} />
    </Elements>
  );
}

function SettledRedirect({ bookingId }) {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  useEffect(() => {
    notifyBookingsChanged();
    if (isAuthenticated) {
      navigate(`/me/bookings/${bookingId}`, { replace: true });
    }
  }, [navigate, bookingId, isAuthenticated]);
  if (isAuthenticated) return null;
  return <GuestSuccess bookingId={bookingId} />;
}

SettledRedirect.propTypes = {
  bookingId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
};

function GuestSuccess({ bookingId }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <section className="guest-success">
      <div className="guest-success__icon" aria-hidden="true">✓</div>
      <h1>{t("payment.success", "To'lov muvaffaqiyatli")}</h1>
      <p>
        {t("payment.booking_confirmed",
          "Bronlash tasdiqlandi. Bron raqami:")}{" "}
        <strong>#{bookingId}</strong>
      </p>
      <p className="muted">
        {t("payment.guest_followup",
          "Bronlaringizni \"Bookings\" bo'limidan kuzatib borishingiz mumkin.")}
      </p>
      <div className="guest-success__actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => navigate("/me/bookings", { replace: true })}
        >
          {t("my_bookings.title", "Mening bronlashlarim")}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate("/", { replace: true })}
        >
          {t("common.back_to_catalogue", "Katalogga qaytish")}
        </button>
      </div>
    </section>
  );
}

GuestSuccess.propTypes = {
  bookingId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
};

function PaymentForm({ draft, draftId }) {
  const stripe = useStripe();
  const elements = useElements();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();

  const [paying, setPaying] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [polling, setPolling] = useState(false);
  const [guestBookingId, setGuestBookingId] = useState(null);
  const [holdExpired, setHoldExpired] = useState(false);

  // When the hold deadline elapses we lock down the form so the user
  // can't trigger a payment we'd then have to refund.
  const handleExpire = () => {
    if (paying || polling) return;  // mid-flight payment must finish on its own
    setHoldExpired(true);
  };

  const handlePay = async () => {
    if (!stripe || !elements || paying) return;
    if (holdExpired) return;
    setPaying(true);
    setErrorMsg(null);

    const { error: submitError } = await elements.submit();
    if (submitError) {
      setErrorMsg(submitError.message || t("payment.failed"));
      setPaying(false);
      return;
    }

    const { error: confirmError } = await stripe.confirmPayment({
      elements,
      clientSecret: draft.client_secret,
      redirect: "if_required",
      confirmParams: {
        // Mini App stays in-app; no return_url needed for "if_required".
      },
    });

    if (confirmError) {
      setErrorMsg(confirmError.message || t("payment.failed"));
      setPaying(false);
      return;
    }

    // Stripe says paid — wait for the webhook to convert the draft.
    setPolling(true);
    const settled = await pollDraftUntilSettled(draftId);
    setPolling(false);
    setPaying(false);

    if (settled.status === "succeeded" && settled.booking_id) {
      if (isAuthenticated) {
        navigate(`/me/bookings/${settled.booking_id}`, { replace: true });
      } else {
        setGuestBookingId(settled.booking_id);
      }
    } else if (settled.status === "failed") {
      setErrorMsg(settled.failure_reason || t("payment.failed"));
    } else {
      setErrorMsg(t("payment.still_processing"));
    }
  };

  useMainButton({
    text: paying || polling ? t("payment.processing") : t("payment.pay_now"),
    visible: !guestBookingId && !holdExpired,
    disabled: !stripe || !elements || holdExpired,
    loading: paying || polling,
    onClick: handlePay,
  });

  if (guestBookingId) {
    return <GuestSuccess bookingId={guestBookingId} />;
  }

  if (holdExpired) {
    return (
      <section className="payment-page">
        <header className="payment-page__header">
          <h1>{t("payment.hold_expired_title", "Time's up")}</h1>
          <p className="muted">
            {t("payment.hold_expired_body",
              "Your 5-minute hold ended. The room is back in the catalogue — please pick dates again.")}
          </p>
        </header>
        <div className="profile-edit__actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate("/me/bookings", { replace: true })}
          >
            {t("nav.bookings", "Bookings")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate("/", { replace: true })}
          >
            {t("booking.browse_rooms", "Browse rooms")}
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="payment-page">
      <BackButton />
      <header className="payment-page__header">
        <h1>{t("payment.title")}</h1>
        <p className="muted">
          {draft.amount} {String(draft.currency).toUpperCase()}
        </p>
        {draft.expires_at && (
          <PaymentCountdown
            expiresAt={draft.expires_at}
            onExpire={handleExpire}
          />
        )}
      </header>

      <div className="payment-page__stripe-card">
        <PaymentElement />
      </div>

      {errorMsg && (
        <div className="form-error" role="alert">{errorMsg}</div>
      )}
      {polling && (
        <p className="muted">{t("payment.confirming")}</p>
      )}

      {/* Fallback CTA for browsers without Telegram MainButton. */}
      <button
        type="button"
        className="btn btn-primary"
        style={{ width: "100%", marginTop: 16 }}
        onClick={handlePay}
        disabled={!stripe || !elements || paying || polling || holdExpired}
      >
        {paying || polling
          ? t("payment.processing", "Processing…")
          : t("booking.pay", "Pay")}
      </button>

      <p className="legal-note">{t("booking.no_refund_notice")}</p>
    </section>
  );
}

const draftShape = PropTypes.shape({
  client_secret: PropTypes.string.isRequired,
  amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  currency: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  expires_at: PropTypes.string,
  intent_status: PropTypes.string,
  status: PropTypes.string,
  booking_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
});

PaymentForm.propTypes = {
  draft: draftShape.isRequired,
  draftId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
};

// ---------------------------------------------------------------------------
// Demo "Pay" form — used when Stripe is not configured. Mirrors PaymentForm
// (header, countdown, hold-expired UX, post-pay polling) but skips Stripe
// Elements entirely; clicking Pay calls /payments/drafts/<id>/demo-confirm/.
// ---------------------------------------------------------------------------
function DemoPaymentForm({ draft, draftId, setDraft }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();

  const [paying, setPaying] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [holdExpired, setHoldExpired] = useState(false);

  const handleExpire = () => {
    if (paying) return;
    setHoldExpired(true);
  };

  const handlePay = async () => {
    if (paying || holdExpired) return;
    setPaying(true);
    setErrorMsg(null);
    try {
      const res = await demoConfirmDraft(draftId);
      notifyBookingsChanged();
      const bookingId = res?.booking_id;
      if (!bookingId) {
        setErrorMsg(t("payment.error_generic", "Could not confirm payment."));
        return;
      }
      if (isAuthenticated) {
        navigate(`/me/bookings/${bookingId}`, { replace: true });
      } else {
        setDraft({ ...draft, booking_id: bookingId, status: "succeeded" });
      }
    } catch (e) {
      const code = e?.response?.data?.code;
      if (code === "hold_expired") setHoldExpired(true);
      setErrorMsg(
        e?.response?.data?.detail || t("payment.error_generic", "Could not confirm payment."),
      );
    } finally {
      setPaying(false);
    }
  };

  useMainButton({
    text: paying ? t("payment.processing", "Processing…") : t("booking.pay", "Pay"),
    visible: !holdExpired,
    disabled: paying || holdExpired,
    onClick: handlePay,
  });

  if (holdExpired) {
    return (
      <section className="payment-page payment-page--expired">
        <h1>{t("payment.hold_expired_title", "Time's up")}</h1>
        <p className="muted">
            {t("payment.hold_expired_body",
            "Your 5-minute hold has expired. Please start a new booking.")}
        </p>
        <div className="payment-page__expired-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate("/me/bookings", { replace: true })}
          >
            {t("nav.bookings", "Bookings")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate("/", { replace: true })}
          >
            {t("booking.browse_rooms", "Browse rooms")}
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="payment-page">
      <BackButton />
      <header className="payment-page__header">
        <h1>{t("payment.title")}</h1>
        <p className="muted">
          {draft.amount} {String(draft.currency).toUpperCase()}
        </p>
        {draft.expires_at && (
          <PaymentCountdown
            expiresAt={draft.expires_at}
            onExpire={handleExpire}
          />
        )}
      </header>

      <div className="payment-page__demo-notice">
        {t("payment.demo_notice",
          "Demo mode: Stripe is not configured. Click Pay to simulate a successful payment.")}
      </div>

      {errorMsg && (
        <div className="form-error" role="alert">{errorMsg}</div>
      )}

      <button
        type="button"
        className="btn btn-primary"
        style={{ width: "100%", marginTop: 16 }}
        onClick={handlePay}
        disabled={paying || holdExpired}
      >
        {paying
          ? t("payment.processing", "Processing…")
          : t("booking.pay", "Pay")}
      </button>

      <p className="legal-note">{t("booking.no_refund_notice")}</p>
    </section>
  );
}

DemoPaymentForm.propTypes = {
  draft: PropTypes.shape({
    amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    currency: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    expires_at: PropTypes.string,
    booking_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    status: PropTypes.string,
    intent_status: PropTypes.string,
  }).isRequired,
  draftId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  setDraft: PropTypes.func.isRequired,
};
