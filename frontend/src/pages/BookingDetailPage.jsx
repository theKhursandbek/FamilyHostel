import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import { getBooking, cancelBooking, checkoutBooking } from "../services/bookingService";
import { getBookingPayments } from "../services/paymentService";
import { useToast } from "../context/ToastContext";
import Button from "../components/Button";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

const STATUS_LABELS = {
  pending: "Pending",
  paid: "Paid",
  completed: "Checked out",
  canceled: "Canceled",
};

const BADGE_MAP = {
  pending: "badge-warning",
  paid: "badge-success",
  completed: "badge-muted",
  canceled: "badge-danger",
};

const SOURCE_LABELS = {
  walk_in: "Walk-in",
  manual: "Manual entry",
  telegram: "Telegram bot",
};

const PAY_METHOD_LABELS = {
  cash: "Cash",
  terminal: "Terminal (POS)",
  qr: "QR code",
  card_transfer: "Card transfer",
};

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span className="info-row-label">{label}</span>
      <span className="info-row-value">{value ?? "—"}</span>
    </div>
  );
}

InfoRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.node]),
};

function StatusBadge({ status }) {
  return (
    <span className={`badge ${BADGE_MAP[status] || "badge-muted"}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

StatusBadge.propTypes = {
  status: PropTypes.string.isRequired,
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

  const handleCancel = async () => {
    if (!globalThis.confirm("Are you sure you want to cancel this booking?")) return;
    setActionLoading(true);
    try {
      await cancelBooking(id);
      toast.success("Booking canceled");
      fetchBooking();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to cancel booking");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckout = async () => {
    if (!globalThis.confirm(
      "Check this guest out?\n\nIf this is BEFORE the scheduled check-out date, " +
      "the unused nights will NOT be refunded.",
    )) return;
    setActionLoading(true);
    try {
      await checkoutBooking(id);
      toast.success("Guest checked out");
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

  // Primary payment method for the header summary (most-recent successful payment).
  const primaryMethod = (() => {
    const paid = payments.filter((p) => p.is_paid);
    if (paid.length === 0) return null;
    // Last by created_at
    const sorted = [...paid].sort((a, b) =>
      String(b.created_at).localeCompare(String(a.created_at)),
    );
    return sorted[0].method;
  })();

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <Button variant="ghost" size="sm" onClick={() => navigate("/bookings")}>
          ← Back
        </Button>
        <h1 style={{ flex: 1 }}>Booking #{booking.id}</h1>
        {booking.source === "telegram" && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: "0.78rem",
              padding: "4px 10px",
              borderRadius: 999,
              background: "#e0f2fe",
              color: "#0369a1",
              fontWeight: 600,
              marginRight: 8,
            }}
          >
            ✈ Telegram
          </span>
        )}
        <StatusBadge status={booking.status} />
      </div>

      {/* Guest card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 className="section-title">Guest</h3>
        <InfoRow label="Name" value={booking.client_name} />
        <InfoRow label="Phone" value={booking.client_phone} />
        <InfoRow label="Passport" value={booking.client_passport} />
      </div>

      {/* Stay card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 className="section-title">Stay</h3>
        <InfoRow label="Room" value={booking.room_number} />
        <InfoRow label="Branch" value={booking.branch_name} />
        <InfoRow label="Check-in" value={booking.check_in_date} />
        <InfoRow label="Check-out" value={booking.check_out_date} />
        <InfoRow label="Booking source" value={SOURCE_LABELS[booking.source] || booking.source || "—"} />
      </div>

      {/* Money card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 className="section-title">Pricing</h3>
        <InfoRow label="Price (per stay)" value={formatPrice(booking.price_at_booking)} />
        <InfoRow label="Discount" value={formatPrice(booking.discount_amount)} />
        <InfoRow
          label="Final Price"
          value={<strong className="text-success">{formatPrice(booking.final_price)}</strong>}
        />
        <InfoRow label="Paid" value={formatPrice(booking.paid_total)} />
        <InfoRow
          label="Balance Due"
          value={
            <strong style={{ color: Number(booking.balance_due) > 0 ? "var(--brand-danger)" : "inherit" }}>
              {formatPrice(booking.balance_due)}
            </strong>
          }
        />
        <InfoRow
          label="Payment method"
          value={primaryMethod ? PAY_METHOD_LABELS[primaryMethod] || primaryMethod : "—"}
        />
      </div>

      {/* Payments history */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 className="section-title">Payment history</h3>
        {payments.length === 0 ? (
          <div className="empty-state" style={{ padding: 16 }}>No payments recorded yet.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Type</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td>{p.created_at ? new Date(p.created_at).toLocaleString() : "—"}</td>
                    <td>{formatPrice(p.amount)}</td>
                    <td>{PAY_METHOD_LABELS[p.method] || p.method || "—"}</td>
                    <td style={{ textTransform: "capitalize" }}>{p.payment_type || "—"}</td>
                    <td>
                      <span className={`badge ${p.is_paid ? "badge-success" : "badge-warning"}`}>
                        {p.is_paid ? "Paid" : "Pending"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Meta card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 className="section-title">Meta</h3>
        <InfoRow label="Status" value={<StatusBadge status={booking.status} />} />
        <InfoRow
          label="Created"
          value={booking.created_at ? new Date(booking.created_at).toLocaleString() : "—"}
        />
        <InfoRow
          label="Updated"
          value={booking.updated_at ? new Date(booking.updated_at).toLocaleString() : "—"}
        />
      </div>

      {/* Actions */}
      {(booking.status === "pending" || booking.status === "paid") && (
        <div className="card">
          <h3 className="section-title">Actions</h3>
          <div style={{ display: "flex", gap: 12 }}>
            {booking.status === "pending" && (
              <Button variant="danger" disabled={actionLoading} onClick={handleCancel}>
                {actionLoading ? "Processing..." : "Cancel Booking"}
              </Button>
            )}
            {booking.status === "paid" && (
              <Button disabled={actionLoading} onClick={handleCheckout}>
                {actionLoading ? "Processing..." : "Checkout"}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default BookingDetailPage;
