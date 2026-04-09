import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getBooking, cancelBooking, completeBooking } from "../services/bookingService";
import Button from "../components/Button";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

const STATUS_LABELS = {
  pending: "Pending",
  paid: "Paid",
  completed: "Completed",
  canceled: "Canceled",
};

const STATUS_COLORS = {
  pending: "#f59e0b",
  paid: "#22c55e",
  completed: "#6b7280",
  canceled: "#ef4444",
};

function InfoRow({ label, value }) {
  return (
    <div style={{ display: "flex", padding: "10px 0", borderBottom: "1px solid #f0f0f0" }}>
      <span style={{ width: 180, fontWeight: 500, color: "#6b7280", flexShrink: 0 }}>{label}</span>
      <span style={{ color: "#1f2937" }}>{value ?? "—"}</span>
    </div>
  );
}

function StatusBadge({ status }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 14px",
        borderRadius: 14,
        fontSize: 13,
        fontWeight: 600,
        color: "#fff",
        backgroundColor: STATUS_COLORS[status] || "#6b7280",
      }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function BookingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
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
      fetchBooking();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to cancel booking");
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!globalThis.confirm("Mark this booking as completed?")) return;
    setActionLoading(true);
    try {
      await completeBooking(id);
      fetchBooking();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to complete booking");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchBooking} />;
  if (!booking) return null;

  const formatPrice = (val) =>
    val === null || val === undefined ? "—" : `${Number(val).toLocaleString()} сум`;

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="sm" onClick={() => navigate("/bookings")}>
          ← Back
        </Button>
        <h1 style={{ margin: 0, flex: 1 }}>Booking #{booking.id}</h1>
        <StatusBadge status={booking.status} />
      </div>

      {/* Info card */}
      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          border: "1px solid #e5e7eb",
          padding: "16px 24px",
          marginBottom: 24,
        }}
      >
        <h3 style={{ margin: "0 0 12px", fontSize: 15, color: "#374151" }}>Booking Details</h3>
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
            <strong style={{ color: "#059669" }}>{formatPrice(booking.final_price)}</strong>
          }
        />
        <InfoRow label="Status" value={<StatusBadge status={booking.status} />} />
        <InfoRow label="Created" value={booking.created_at ? new Date(booking.created_at).toLocaleString() : "—"} />
        <InfoRow label="Updated" value={booking.updated_at ? new Date(booking.updated_at).toLocaleString() : "—"} />
      </div>

      {/* Actions */}
      {(booking.status === "pending" || booking.status === "paid") && (
        <div
          style={{
            background: "#fff",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            padding: "16px 24px",
          }}
        >
          <h3 style={{ margin: "0 0 12px", fontSize: 15, color: "#374151" }}>Actions</h3>
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
