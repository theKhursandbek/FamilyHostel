import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { getDirectorDashboard } from "../../services/dashboardService";
import { useSocket } from "../../hooks/useSocket";
import StatCard from "../../components/StatCard";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const fmt = (n) => Number(n || 0).toLocaleString();

function Row({ label, value, color, bold }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 14,
    }}>
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {color && (
          <span style={{
            width: 8, height: 8, borderRadius: "50%",
            background: color, flexShrink: 0,
          }} />
        )}
        <span className="text-muted">{label}</span>
      </span>
      <span style={{ fontWeight: bold ? 700 : 600 }}>{value}</span>
    </div>
  );
}
Row.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  color: PropTypes.string,
  bold: PropTypes.bool,
};

function DirectorDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getDirectorDashboard());
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load director dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  useSocket("director", {
    booking_created:       () => fetchDashboard(),
    payment_completed:     () => fetchDashboard(),
    cleaning_task_updated: () => fetchDashboard(),
    attendance_updated:    () => fetchDashboard(),
  });

  if (loading) return <Loader message="Loading director dashboard..." />;
  if (error)   return <ErrorMessage message={error} onRetry={fetchDashboard} />;
  if (!data)   return <div className="empty-state">No dashboard data available.</div>;

  const branch     = data.branch || {};
  const revenue    = data.revenue || {};
  const today      = data.booking_stats?.today || {};
  const month      = data.booking_stats?.month || {};
  const attendance = data.attendance_summary || {};
  const issues     = data.pending_issues || {};
  const perf       = data.staff_performance || [];

  const attendanceTotal = (attendance.present ?? 0) + (attendance.late ?? 0) + (attendance.absent ?? 0);
  const presentPct = attendanceTotal
    ? Math.round(((attendance.present ?? 0) / attendanceTotal) * 100)
    : 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 style={{ marginBottom: 4 }}>Director Dashboard</h1>
          {branch.name && (
            <span className="text-muted" style={{ fontSize: 14 }}>{branch.name}</span>
          )}
        </div>
      </div>

      <div className="stat-grid">
        <StatCard
          title="Revenue Today"
          value={`${fmt(revenue.today)} UZS`}
          subtitle={`${fmt(revenue.month)} UZS this month`}
        />
        <StatCard
          title="Bookings Today"
          value={today.total ?? 0}
          subtitle={`${today.paid ?? 0} paid · ${today.pending ?? 0} pending · ${today.canceled ?? 0} canceled`}
        />
        <StatCard
          title="Bookings This Month"
          value={month.total ?? 0}
          subtitle={`${month.paid ?? 0} paid · ${month.canceled ?? 0} canceled`}
        />
        <StatCard
          title="Pending Issues"
          value={(issues.cleaning_retries ?? 0) + (issues.pending_cleaning ?? 0)}
          subtitle={`${issues.cleaning_retries ?? 0} retries · ${issues.pending_cleaning ?? 0} pending tasks`}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
        <div className="card" style={{ margin: 0 }}>
          <h3 className="section-title" style={{ marginTop: 0 }}>Today's Bookings</h3>
          <Row label="Paid"     value={today.paid ?? 0}     color="#22c55e" />
          <Row label="Pending"  value={today.pending ?? 0}  color="#f59e0b" />
          <Row label="Canceled" value={today.canceled ?? 0} color="#ef4444" />
          <Row label="Total"    value={today.total ?? 0}    bold />
        </div>

        <div className="card" style={{ margin: 0 }}>
          <h3 className="section-title" style={{ marginTop: 0 }}>Attendance Today</h3>
          {attendanceTotal === 0 ? (
            <p className="text-muted" style={{ fontSize: 13, margin: "12px 0 0" }}>
              No attendance recorded yet for today.
            </p>
          ) : (
            <>
              <Row label="Present"  value={`${attendance.present ?? 0} (${presentPct}%)`} color="#22c55e" />
              <Row label="Late"     value={attendance.late ?? 0}    color="#f59e0b" />
              <Row label="Absent"   value={attendance.absent ?? 0}  color="#ef4444" />
              <Row label="Total"    value={attendanceTotal}         bold />
            </>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 className="section-title" style={{ marginTop: 0 }}>Staff Performance (this month)</h3>
        {perf.length === 0 ? (
          <p className="text-muted" style={{ fontSize: 13, margin: "12px 0 0" }}>
            No completed cleaning tasks recorded yet this month.
          </p>
        ) : (
          <div>
            {perf.map((p) => (
              <Row
                key={p.staff_id || p.staff_name}
                label={p.staff_name}
                value={`${fmt(p.tasks_completed ?? 0)} done · ${fmt(p.tasks_retried ?? 0)} retried`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DirectorDashboard;
