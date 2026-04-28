import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { getAdminDashboard } from "../../services/dashboardService";
import { useSocket } from "../../hooks/useSocket";
import StatCard from "../../components/StatCard";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmt(n) {
  return Number(n || 0).toLocaleString();
}

function diffColor(diff) {
  if (diff < 0) return "#ef4444";
  if (diff > 0) return "#22c55e";
  return "var(--text-primary)";
}

function cashSessionStatus(session) {
  if (!session) return "None";
  return session.end_time ? "Closed" : "Open";
}

// Pill badge
const BADGE_COLORS = {
  day:    { bg: "#fef3c7", text: "#92400e" },
  night:  { bg: "#e0e7ff", text: "#3730a3" },
  open:   { bg: "#d1fae5", text: "#065f46" },
  closed: { bg: "#fee2e2", text: "#991b1b" },
};

function Badge({ label, color }) {
  const c = BADGE_COLORS[color] || { bg: "#e5e7eb", text: "#374151" };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600,
      background: c.bg, color: c.text,
    }}>
      {label}
    </span>
  );
}
Badge.propTypes = {
  label: PropTypes.string.isRequired,
  color: PropTypes.string,
};

// Horizontal stacked bar for room statuses
const ROOM_SEGMENTS = [
  { key: "available", label: "Available", color: "#22c55e" },
  { key: "booked",    label: "Booked",    color: "#3b82f6" },
  { key: "occupied",  label: "Occupied",  color: "#f59e0b" },
  { key: "cleaning",  label: "Cleaning",  color: "#a855f7" },
];

function RoomBar({ rooms }) {
  const total = rooms?.total || 0;
  if (!total) return <p className="text-muted" style={{ fontSize: 13 }}>No rooms.</p>;

  return (
    <div>
      <div style={{ display: "flex", borderRadius: 6, overflow: "hidden", height: 14, marginBottom: 10 }}>
        {ROOM_SEGMENTS.map(({ key, color }) => {
          const count = rooms[key] || 0;
          const pct = (count / total) * 100;
          if (!pct) return null;
          return (
            <div
              key={key}
              title={`${key}: ${count}`}
              style={{ width: `${pct}%`, background: color, transition: "width 0.4s ease" }}
            />
          );
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px" }}>
        {ROOM_SEGMENTS.map(({ key, label, color }) => {
          const count = rooms[key] || 0;
          return (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
              <span className="text-muted">{label}</span>
              <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
RoomBar.propTypes = {
  rooms: PropTypes.shape({
    total:     PropTypes.number,
    available: PropTypes.number,
    booked:    PropTypes.number,
    occupied:  PropTypes.number,
    cleaning:  PropTypes.number,
  }),
};

// Booking status row
function BookingRow({ label, count, color }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "8px 0", borderBottom: "1px solid var(--border)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
        <span style={{ fontSize: 14 }}>{label}</span>
      </div>
      <span style={{ fontWeight: 700, fontSize: 15 }}>{count}</span>
    </div>
  );
}
BookingRow.propTypes = {
  label: PropTypes.string.isRequired,
  count: PropTypes.number.isRequired,
  color: PropTypes.string.isRequired,
};

// Detail row inside cash card
function CashRow({ label, value }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between",
      padding: "7px 0", borderBottom: "1px solid var(--border)", fontSize: 14,
    }}>
      <span className="text-muted">{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}
CashRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
};

// Cash session detail card
function CashCard({ session }) {
  if (!session) {
    return (
      <div style={{ padding: "28px 0", textAlign: "center", color: "var(--text-secondary)", fontSize: 14 }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>💰</div>
        No cash session started today.
      </div>
    );
  }

  const isOpen = !session.end_time;
  const diff   = session.difference == null ? null : Number(session.difference);
  const shiftLabel = session.shift_type === "night" ? "Night shift" : "Day shift";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Badge label={shiftLabel} color={session.shift_type} />
        <Badge label={isOpen ? "Open" : "Closed"} color={isOpen ? "open" : "closed"} />
      </div>
      <CashRow label="Opening balance" value={`${fmt(session.opening_balance)} UZS`} />
      <CashRow
        label="Closing balance"
        value={session.closing_balance == null ? "—" : `${fmt(session.closing_balance)} UZS`}
      />
      {diff !== null && (
        <div style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", fontSize: 14 }}>
          <span className="text-muted">Difference</span>
          <span style={{ fontWeight: 700, color: diffColor(diff) }}>
            {diff > 0 ? "+" : ""}{fmt(diff)} UZS
          </span>
        </div>
      )}
      {session.start_time && (
        <p className="text-muted" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
          Started: {new Date(session.start_time).toLocaleTimeString()}
          {session.end_time ? ` · Closed: ${new Date(session.end_time).toLocaleTimeString()}` : ""}
        </p>
      )}
    </div>
  );
}
CashCard.propTypes = {
  session: PropTypes.shape({
    shift_type:      PropTypes.string,
    start_time:      PropTypes.string,
    end_time:        PropTypes.string,
    opening_balance: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    closing_balance: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    difference:      PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  }),
};

// ===========================================================================
// Main component
// ===========================================================================
function AdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getAdminDashboard();
      setData(result);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  useSocket("admin", {
    booking_created:       () => fetchDashboard(),
    payment_completed:     () => fetchDashboard(),
    cleaning_task_updated: () => fetchDashboard(),
    attendance_updated:    () => fetchDashboard(),
  });

  if (loading) return <Loader message="Loading dashboard..." />;
  if (error)   return <ErrorMessage message={error} onRetry={fetchDashboard} />;
  if (!data)   return <div className="empty-state">No dashboard data available.</div>;

  const bookings = data.bookings_today || {};
  const rooms    = data.active_rooms  || {};
  const shift    = data.current_shift;
  const sessionStatus = cashSessionStatus(data.cash_session);

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 style={{ marginBottom: 4 }}>Dashboard</h1>
          {data.branch && (
            <span className="text-muted" style={{ fontSize: 14 }}>{data.branch.name}</span>
          )}
        </div>
        {shift && (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Badge
              label={shift.shift_type === "night" ? "🌙 Night shift" : "☀️ Day shift"}
              color={shift.shift_type}
            />
            <span className="text-muted" style={{ fontSize: 13 }}>
              {new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
            </span>
          </div>
        )}
      </div>

      {/* ── Top stat cards ── */}
      <div className="stat-grid">
        <StatCard
          title="Bookings Today"
          value={bookings.total ?? 0}
          subtitle={`${bookings.paid ?? 0} paid · ${bookings.pending ?? 0} pending · ${bookings.canceled ?? 0} canceled`}
        />
        <StatCard
          title="Revenue Today"
          value={`${fmt(data.revenue_today)} UZS`}
        />
        <StatCard
          title="Total Rooms"
          value={rooms.total ?? 0}
          subtitle={`${rooms.available ?? 0} available · ${rooms.occupied ?? 0} occupied`}
        />
        <StatCard
          title="Cash Session"
          value={sessionStatus}
          subtitle={
            data.cash_session
              ? `${fmt(data.cash_session.opening_balance)} UZS opening`
              : "No session today"
          }
        />
      </div>

      {/* ── Second row: booking breakdown + room occupancy ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
        <div className="card" style={{ margin: 0 }}>
          <h3 className="section-title" style={{ marginTop: 0 }}>Booking Status</h3>
          <BookingRow label="Paid"     count={bookings.paid ?? 0}     color="#22c55e" />
          <BookingRow label="Pending"  count={bookings.pending ?? 0}  color="#f59e0b" />
          <BookingRow label="Canceled" count={bookings.canceled ?? 0} color="#ef4444" />
          <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0 0", fontSize: 14 }}>
            <span style={{ fontWeight: 600 }}>Total</span>
            <span style={{ fontWeight: 700, fontSize: 16 }}>{bookings.total ?? 0}</span>
          </div>
        </div>

        <div className="card" style={{ margin: 0 }}>
          <h3 className="section-title" style={{ marginTop: 0 }}>Room Occupancy</h3>
          <RoomBar rooms={rooms} />
        </div>
      </div>

      {/* ── Cash session detail ── */}
      <div className="card" style={{ marginTop: 16 }}>
        <h3 className="section-title" style={{ marginTop: 0 }}>Cash Session</h3>
        <CashCard session={data.cash_session} />
      </div>
    </div>
  );
}

export default AdminDashboard;
