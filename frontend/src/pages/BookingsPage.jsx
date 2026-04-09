import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getBookings, createBooking, cancelBooking, completeBooking } from "../services/bookingService";
import Table from "../components/Table";
import Modal from "../components/Modal";
import BookingForm from "../components/BookingForm";
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

const columns = [
  { key: "room_number", label: "Room" },
  { key: "client_name", label: "Client" },
  { key: "check_in_date", label: "Check-in" },
  { key: "check_out_date", label: "Check-out" },
  {
    key: "status",
    label: "Status",
    render: (val) => (
      <span className={`badge ${BADGE_MAP[val] || "badge-muted"}`}>
        {STATUS_LABELS[val] || val}
      </span>
    ),
  },
  {
    key: "final_price",
    label: "Price",
    render: (val) => (val === null || val === undefined ? "—" : `${Number(val).toLocaleString()} сум`),
  },
];

function BookingsPage() {
  const navigate = useNavigate();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [cancellingId, setCancellingId] = useState(null);
  const [completingId, setCompletingId] = useState(null);

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBookings();
      setBookings(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load bookings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  const handleCreate = async (formData) => {
    setCreating(true);
    try {
      await createBooking(formData);
      setIsModalOpen(false);
      fetchBookings();
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.detail || detail?.non_field_errors?.[0] || "Failed to create booking";
      alert(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleCancel = async (booking) => {
    if (booking.status !== "pending") return;
    if (!globalThis.confirm(`Cancel booking for room ${booking.room_number}?`)) return;
    setCancellingId(booking.id);
    try {
      await cancelBooking(booking.id);
      fetchBookings();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to cancel booking");
    } finally {
      setCancellingId(null);
    }
  };

  const handleComplete = async (booking) => {
    if (booking.status !== "paid") return;
    if (!globalThis.confirm(`Complete booking for room ${booking.room_number}?`)) return;
    setCompletingId(booking.id);
    try {
      await completeBooking(booking.id);
      fetchBookings();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to complete booking");
    } finally {
      setCompletingId(null);
    }
  };

  const columnsWithActions = [
    ...columns,
    {
      key: "_actions",
      label: "",
      render: (_, row) => (
        <div style={{ display: "flex", gap: 6 }}>
          {row.status === "pending" && (
            <Button
              variant="danger"
              size="sm"
              disabled={cancellingId === row.id}
              onClick={(e) => {
                e.stopPropagation();
                handleCancel(row);
              }}
            >
              {cancellingId === row.id ? "…" : "Cancel"}
            </Button>
          )}
          {row.status === "paid" && (
            <Button
              variant="secondary"
              size="sm"
              disabled={completingId === row.id}
              onClick={(e) => {
                e.stopPropagation();
                handleComplete(row);
              }}
            >
              {completingId === row.id ? "…" : "Complete"}
            </Button>
          )}
        </div>
      ),
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchBookings} />;

  return (
    <div>
      <div className="page-header">
        <h1>Bookings</h1>
        <Button onClick={() => setIsModalOpen(true)}>+ New Booking</Button>
      </div>

      <Table
        columns={columnsWithActions}
        data={bookings}
        emptyMessage="No bookings found"
        onRowClick={(row) => navigate(`/bookings/${row.id}`)}
      />

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Booking"
      >
        <BookingForm onSubmit={handleCreate} loading={creating} />
      </Modal>
    </div>
  );
}

export default BookingsPage;
