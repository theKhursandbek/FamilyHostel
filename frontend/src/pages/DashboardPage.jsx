import { useState, useEffect, useCallback } from "react";
import { getAdminDashboard } from "../services/dashboardService";
import { useSocket } from "../hooks/useSocket";
import StatCard from "../components/StatCard";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

function DashboardPage() {
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
      setError(
        err.response?.data?.detail || "Failed to load dashboard data."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Real-time updates via WebSocket
  useSocket("admin", {
    booking_created: () => fetchDashboard(),
    payment_completed: () => fetchDashboard(),
    cleaning_task_updated: () => fetchDashboard(),
    attendance_updated: () => fetchDashboard(),
  });

  if (loading) {
    return <Loader message="Loading dashboard..." />;
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={fetchDashboard} />;
  }

  if (!data) {
    return <div className="empty-state">No dashboard data available.</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        {data.branch && (
          <span className="text-secondary" style={{ fontSize: 14 }}>
            {data.branch.name}
          </span>
        )}
      </div>

      {/* Stat cards */}
      <div className="stat-grid">
        <StatCard
          title="Today's Bookings"
          value={data.bookings_today?.total ?? 0}
          subtitle={`${data.bookings_today?.paid ?? 0} paid · ${data.bookings_today?.pending ?? 0} pending`}
        />
        <StatCard
          title="Revenue Today"
          value={`${Number(data.revenue_today || 0).toLocaleString()} UZS`}
        />
        <StatCard
          title="Active Rooms"
          value={data.active_rooms?.total ?? 0}
          subtitle={`${data.active_rooms?.available ?? 0} available · ${data.active_rooms?.occupied ?? 0} occupied`}
        />
        <StatCard
          title="Cash Session"
          value={data.cash_session ? data.cash_session.shift_type : "No session"}
          subtitle={
            data.cash_session
              ? `Balance: ${Number(data.cash_session.opening_balance || 0).toLocaleString()} UZS`
              : "Not started"
          }
        />
      </div>

      {/* Current shift info */}
      {data.current_shift && (
        <div className="alert alert-info">
          <p style={{ margin: 0, fontWeight: 500 }}>
            Current Shift: {data.current_shift.shift_type} —{" "}
            {data.current_shift.role}
          </p>
        </div>
      )}
    </div>
  );
}

export default DashboardPage;
