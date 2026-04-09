import { useState, useEffect, useCallback } from "react";
import { getDirectorDashboard } from "../../services/dashboardService";
import StatCard from "../../components/StatCard";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const performanceColumns = [
  { key: "staff_name", label: "Staff" },
  {
    key: "tasks_completed",
    label: "Tasks Completed",
    render: (val) => val ?? 0,
  },
  {
    key: "tasks_retried",
    label: "Retries",
    render: (val) => val ?? 0,
  },
];

const attendanceColumns = [
  { key: "staff_name", label: "Staff" },
  { key: "days_present", label: "Present", render: (val) => val ?? 0 },
  { key: "days_absent", label: "Absent", render: (val) => val ?? 0 },
  { key: "days_off", label: "Days Off", render: (val) => val ?? 0 },
];

const issueColumns = [
  {
    key: "type",
    label: "Type",
    render: (val) => (
      <span
        style={{
          padding: "2px 8px",
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 600,
          color: "#fff",
          backgroundColor: val === "retry" ? "#ef4444" : "#f59e0b",
        }}
      >
        {val === "retry" ? "Cleaning Retry" : "Penalty"}
      </span>
    ),
  },
  { key: "description", label: "Description" },
  { key: "staff_name", label: "Staff" },
  { key: "date", label: "Date" },
];

function DirectorDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getDirectorDashboard();
      setData(result);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load director dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) return <Loader message="Loading director dashboard..." />;
  if (error) return <ErrorMessage message={error} onRetry={fetchDashboard} />;
  if (!data) return null;

  const revenueToday = data.revenue_today ?? data.revenue?.today ?? 0;
  const revenueMonth = data.revenue_month ?? data.revenue?.month ?? 0;
  const totalBookings = data.total_bookings ?? data.bookings?.total ?? 0;
  const activeBookings = data.active_bookings ?? data.bookings?.active ?? 0;
  const pendingRetries = data.pending_retries ?? data.cleaning_retries ?? 0;
  const totalPenalties = data.total_penalties ?? data.penalties_count ?? 0;
  const staffPerformance = data.staff_performance ?? [];
  const attendance = data.attendance ?? [];
  const pendingIssues = data.pending_issues ?? [];

  return (
    <div>
      <h2 style={{ margin: "0 0 24px" }}>🏢 Director Dashboard</h2>

      {/* Revenue & Booking cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
          marginBottom: 28,
        }}
      >
        <StatCard
          title="Revenue Today"
          value={`${Number(revenueToday).toLocaleString()} UZS`}
        />
        <StatCard
          title="Revenue This Month"
          value={`${Number(revenueMonth).toLocaleString()} UZS`}
        />
        <StatCard
          title="Total Bookings"
          value={totalBookings}
          subtitle={`${activeBookings} active`}
        />
        <StatCard
          title="Pending Issues"
          value={pendingRetries + totalPenalties}
          subtitle={`${pendingRetries} retries · ${totalPenalties} penalties`}
        />
      </div>

      {/* Staff Performance */}
      <div style={{ marginBottom: 28 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>
          👷 Staff Performance
        </h3>
        <Table
          columns={performanceColumns}
          data={staffPerformance}
          emptyMessage="No staff performance data"
        />
      </div>

      {/* Attendance */}
      <div style={{ marginBottom: 28 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>
          📋 Attendance Summary
        </h3>
        <Table
          columns={attendanceColumns}
          data={attendance}
          emptyMessage="No attendance data"
        />
      </div>

      {/* Pending Issues */}
      {pendingIssues.length > 0 && (
        <div>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>
            ⚠️ Pending Issues
          </h3>
          <Table
            columns={issueColumns}
            data={pendingIssues}
            emptyMessage="No pending issues"
          />
        </div>
      )}
    </div>
  );
}

export default DirectorDashboard;
