import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import { getBooking, checkoutBooking } from "../services/bookingService";
import { getBookingPayments } from "../services/paymentService";
import { useToast } from "../context/ToastContext";
import Button from "../components/Button";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";
import ConfirmDialog from "../components/ConfirmDialog";

const STATUS_LABELS = {
  paid: "Paid",
  completed: "Checked out",
  canceled: "Canceled",
};

// Booking origin channels. Telegram bookings are taken & paid *online*, so the
// money ledger surfaces them as "Online" (the channel badge shows "Telegram").
const SOURCE_LABELS = {
  walk_in: "Walk-in",
  manual: "Manual entry",
  telegram: "Online",
};

const PAY_METHOD_LABELS = {
  cash: "Cash",
  terminal: "Terminal (POS)",
  qr: "QR code",
  card_transfer: "Card transfer",
};

// Online (Stripe / Telegram) payments don't have a physical cash method, so
// the ledger shows them as "Online".
const payMethodLabel = (p) => {
  if (p.payment_type === "online") return "Online";
  return PAY_METHOD_LABELS[p.method] || p.method || "—";
};

const fmtDate = (s) => {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString(undefined, {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return s;
  }
};

const nightsBetween = (a, b) => {
  if (!a || !b) return 0;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / (1000 * 60 * 60 * 24)));
};

// True when checkout happens before the scheduled check-out date (no refund).
const isEarlyCheckout = (booking) => {
  if (!booking?.check_out_date) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const co = new Date(booking.check_out_date);
  co.setHours(0, 0, 0, 0);
  return today < co;
};

// Most-recent successful payment (for the billing summary line).
const latestPaidPayment = (payments) => {
  const paid = payments.filter((p) => p.is_paid);
  if (paid.length === 0) return null;
  return [...paid].sort((a, b) =>
    String(b.created_at).localeCompare(String(a.created_at)),
  )[0];
};

// Telegram bookings are paid online → ledger label is always "Online".
const resolvePrimaryMethodLabel = (booking, payments) => {
  if (booking.source === "telegram") return "Online";
  const last = latestPaidPayment(payments);
  return last ? payMethodLabel(last) : "—";
};

/** Payment statement rows (paid + pending). */
function PaymentHistoryPanel({ payments, formatPrice }) {
  return (
    <section className="bk-panel">
      <h3 className="bk-panel__title">Payment history</h3>
      {payments.length === 0 ? (
        <p className="bk-panel__empty">No payments recorded yet.</p>
      ) : (
        <ul className="bk-pays">
          {payments.map((p) => (
            <li className={`bk-pays__row ${p.is_paid ? "is-paid" : "is-pending"}`} key={p.id}>
              <div className="bk-pays__main">
                <span className="bk-pays__amt">{formatPrice(p.amount)}</span>
                <span className="bk-pays__method">
                  {payMethodLabel(p)}
                  {p.payment_type && p.payment_type !== "online" ? ` · ${p.payment_type}` : ""}
                </span>
              </div>
              <div className="bk-pays__side">
                <span className={`bk-pays__tag ${p.is_paid ? "is-paid" : "is-pending"}`}>
                  {p.is_paid ? "Paid" : "Pending"}
                </span>
                {p.created_at && (
                  <span className="bk-pays__date">{new Date(p.created_at).toLocaleString()}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

PaymentHistoryPanel.propTypes = {
  payments: PropTypes.array.isRequired,
  formatPrice: PropTypes.func.isRequired,
};

/** Right-hand billing statement. */
function BillingPanel({ booking, formatPrice, primaryMethodLabel }) {
  const balanceDue = Number(booking.balance_due ?? 0);
  const discountAmt = Number(booking.discount_amount ?? 0);
  const discountText = discountAmt > 0
    ? `− ${formatPrice(booking.discount_amount)}`
    : formatPrice(booking.discount_amount);
  return (
    <aside className="bk-bill">
      <h3 className="bk-bill__title">Billing</h3>
      <div className="bk-bill__lines">
        <div className="bk-bill__line">
          <span>Price (per stay)</span>
          <span>{formatPrice(booking.price_at_booking)}</span>
        </div>
        <div className="bk-bill__line">
          <span>Discount</span>
          <span>{discountText}</span>
        </div>
        <div className="bk-bill__line bk-bill__line--total">
          <span>Total</span>
          <span>{formatPrice(booking.final_price)}</span>
        </div>
        <div className="bk-bill__line">
          <span>Paid</span>
          <span>{formatPrice(booking.paid_total)}</span>
        </div>
      </div>
      <div className={`bk-bill__balance ${balanceDue > 0 ? "is-due" : "is-clear"}`}>
        <span className="bk-bill__balance-lbl">Balance due</span>
        <span className="bk-bill__balance-val">{formatPrice(booking.balance_due)}</span>
      </div>
      <div className="bk-bill__method">
        <span>Payment method</span>
        <span>{primaryMethodLabel}</span>
      </div>
    </aside>
  );
}

BillingPanel.propTypes = {
  booking: PropTypes.object.isRequired,
  formatPrice: PropTypes.func.isRequired,
  primaryMethodLabel: PropTypes.string.isRequired,
};

function BookingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [booking, setBooking] = useState(null);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  const fetchBooking = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, pays] = await Promise.all([
        getBooking(id),
        getBookingPayments(id).catch(() => []),
      ]);
      setBooking(data);
      setPayments(Array.isArray(pays) ? pays : []);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load booking");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchBooking();
  }, [fetchBooking]);

  const confirmCheckout = async () => {
    setActionLoading(true);
    try {
      await checkoutBooking(id);
      toast.success("Guest checked out");
      setCheckoutOpen(false);
      fetchBooking();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to check out");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchBooking} />;
  if (!booking) return <div className="empty-state">Booking not found.</div>;

  const formatPrice = (val) =>
    val === null || val === undefined ? "—" : `${Number(val).toLocaleString()} сум`;

  const primaryMethodLabel = resolvePrimaryMethodLabel(booking, payments);

  const status = booking.status || "paid";
  const nights = nightsBetween(booking.check_in_date, booking.check_out_date);
  const early = isEarlyCheckout(booking);
  const checkoutMsg = early
    ? `Early checkout for room ${booking.room_number}. The unused nights will NOT be refunded.`
    : `Check out room ${booking.room_number}?`;

  return (
    <div className="bk-detail">
      {/* Top bar — back + primary actions */}
      <div className="bk-detail__bar">
        <Button variant="secondary" size="sm" onClick={() => navigate("/bookings")}>
          ← Back to bookings
        </Button>
        <div className="bk-detail__bar-actions">
          {status === "paid" && (
            <Button size="sm" disabled={actionLoading} onClick={() => setCheckoutOpen(true)}>
              {actionLoading ? "Processing…" : "Check out"}
            </Button>
          )}
        </div>
      </div>

      {/* Hero — room, guest, status, dates */}
      <div className={`bk-detail__hero is-${status}`}>
        <span className="bk-detail__hero-room">{String(booking.room_number ?? "—")}</span>
        <div className="bk-detail__hero-main">
          <div className="bk-detail__hero-top">
            <h1 className="bk-detail__hero-name">{booking.client_name || "Guest"}</h1>
            <span className={`bk-card__status is-${status}`}>
              {STATUS_LABELS[status] || status}
            </span>
          </div>
          <div className="bk-detail__hero-meta">
            <span>Booking #{booking.branch_number ?? booking.id}</span>
            {booking.branch_name && <span>· {booking.branch_name}</span>}
            <span>· {SOURCE_LABELS[booking.source] || booking.source || "—"}</span>
            {booking.source === "telegram" && (
              <span className="bk-detail__tg">✈ Telegram</span>
            )}
          </div>
          <div className="bk-detail__hero-dates">
            <div className="bk-detail__leg">
              <span className="bk-detail__leg-lbl">Check-in</span>
              <span className="bk-detail__leg-val">{fmtDate(booking.check_in_date)}</span>
            </div>
            <span className="bk-detail__leg-sep">
              {nights} night{nights === 1 ? "" : "s"}
            </span>
            <div className="bk-detail__leg bk-detail__leg--end">
              <span className="bk-detail__leg-lbl">Check-out</span>
              <span className="bk-detail__leg-val">{fmtDate(booking.check_out_date)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Body — details (left) + billing statement (right) */}
      <div className="bk-folio">
        <div className="bk-folio__main">
          <section className="bk-panel">
            <h3 className="bk-panel__title">Guest</h3>
            <div className="bk-info">
              <div className="bk-info__cell">
                <span className="bk-info__lbl">Name</span>
                <span className="bk-info__val">{booking.client_name || "—"}</span>
              </div>
              <div className="bk-info__cell">
                <span className="bk-info__lbl">Phone</span>
                <span className="bk-info__val">{booking.client_phone || "—"}</span>
              </div>
              <div className="bk-info__cell">
                <span className="bk-info__lbl">Passport</span>
                <span className="bk-info__val">{booking.client_passport || "—"}</span>
              </div>
              <div className="bk-info__cell">
                <span className="bk-info__lbl">Date of birth</span>
                <span className="bk-info__val">{fmtDate(booking.client_dob)}</span>
              </div>
            </div>
          </section>

          <PaymentHistoryPanel payments={payments} formatPrice={formatPrice} />
        </div>

        <BillingPanel
          booking={booking}
          formatPrice={formatPrice}
          primaryMethodLabel={primaryMethodLabel}
        />
      </div>

      {/* Footnote meta */}
      <p className="bk-detail__foot">
        Created {booking.created_at ? new Date(booking.created_at).toLocaleString() : "—"}
        {booking.updated_at ? ` · Updated ${new Date(booking.updated_at).toLocaleString()}` : ""}
      </p>

      {/* Checkout confirmation (warns on early checkout — no refund) */}
      <ConfirmDialog
        isOpen={checkoutOpen}
        onClose={() => setCheckoutOpen(false)}
        onConfirm={confirmCheckout}
        title="Check out guest?"
        tone={early ? "danger" : "primary"}
        confirmLabel="Check out"
        loading={actionLoading}
        message={checkoutMsg}
      />
    </div>
  );
}

export default BookingDetailPage;
