import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import { getBooking, cancelBooking, completeBooking } from "../services/bookingService";
import { useToast } from "../context/ToastContext";
import Button from "../components/Button";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

const STATUS_LABELS = {
  pending: "Pending",
  paid: "Paid",
  completed: "Completed",
  canceled: "Canceled",
};

const BADGE_MAP = {
  pending: "badge-warning",
  paid: "badge-success",
  completed: "badge-muted",
  canceled: "badge-danger",
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchBooking = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBooking(id);
      setBooking(data);
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

  const handleComplete = async () => {
    if (!globalThis.confirm("Mark this booking as completed?")) return;
    setActionLoading(true);
    try {
      await completeBooking(id);
      toast.success("Booking completed");
      fetchBooking();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to complete booking");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchBooking} />;
  if (!booking) return <div className="empty-state">Booking not found.</div>;

  const formatPrice = (val) =>
    val === null || val === undefined ? "—" : `${Number(val).toLocaleString()} сум`;

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <Button variant="ghost" size="sm" onClick={() => navigate("/bookings")}>
          ← Back
        </Button>
        <h1 style={{ flex: 1 }}>Booking #{booking.id}</h1>
        <StatusBadge status={booking.status} />
      </div>

      {/* Info card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 className="section-title">Booking Details</h3>
        <InfoRow label="Room" value={booking.room_number} />
        <InfoRow label="Client" value={booking.client_name} />
        <InfoRow label="Branch" value={booking.branch_name} />
        <InfoRow label="Check-in" value={booking.check_in_date} />
        <InfoRow label="Check-out" value={booking.check_out_date} />
        <InfoRow label="Price" value={formatPrice(booking.price_at_booking)} />
        <InfoRow label="Discount" value={formatPrice(booking.discount_amount)} />
        <InfoRow
          label="Final Price"
          value={
            <strong className="text-success">{formatPrice(booking.final_price)}</strong>
          }
        />
        <InfoRow label="Status" value={<StatusBadge status={booking.status} />} />
        <InfoRow label="Created" value={booking.created_at ? new Date(booking.created_at).toLocaleString() : "—"} />
        <InfoRow label="Updated" value={booking.updated_at ? new Date(booking.updated_at).toLocaleString() : "—"} />
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
              <Button disabled={actionLoading} onClick={handleComplete}>
                {actionLoading ? "Processing..." : "Complete Booking"}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default BookingDetailPage;
