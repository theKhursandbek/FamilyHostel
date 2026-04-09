import { useState, useEffect, useCallback } from "react";
import { getSuperAdminDashboard } from "../../services/dashboardService";
import StatCard from "../../components/StatCard";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const branchColumns = [
  { key: "name", label: "Branch" },
  {
    key: "revenue",
    label: "Revenue",
    render: (val) =>
      val !== null && val !== undefined
        ? `${Number(val).toLocaleString()} UZS`
        : "—",
  },
  {
    key: "bookings_count",
    label: "Bookings",
    render: (val) => val ?? 0,
  },
  {
    key: "staff_count",
    label: "Staff",
    render: (val) => val ?? 0,
  },
];

const activityColumns = [
  { key: "action", label: "Action" },
  { key: "user_name", label: "User" },
  { key: "branch_name", label: "Branch" },
  {
    key: "created_at",
    label: "Time",
    render: (val) => (val ? new Date(val).toLocaleString() : "—"),
  },
];

function SuperAdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getSuperAdminDashboard();
      setData(result);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load super admin dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) return <Loader message="Loading super admin dashboard..." />;
  if (error) return <ErrorMessage message={error} onRetry={fetchDashboard} />;
  if (!data) return null;

  const totalBranches = data.total_branches ?? data.branches_count ?? 0;
  const totalRevenue = data.total_revenue ?? 0;
  const topBranch = data.top_branch ?? null;
  const totalStaff = data.total_staff ?? 0;
  const totalAdmins = data.total_admins ?? 0;
  const branchList = data.branches ?? [];
  const activityLog = data.activity ?? data.recent_activity ?? [];

  return (
    <div>
      <div className="page-header"><h1>🛡️ Super Admin Dashboard</h1></div>

      {/* Summary cards */}
      <div className="stat-grid">
        <StatCard
          title="Total Branches"
          value={totalBranches}
        />
        <StatCard
          title="Total Revenue"
          value={`${Number(totalRevenue).toLocaleString()} UZS`}
        />
        <StatCard
          title="Top Branch"
          value={topBranch?.name || "—"}
          subtitle={
            topBranch?.revenue
              ? `${Number(topBranch.revenue).toLocaleString()} UZS`
              : undefined
          }
        />
        <StatCard
          title="Staff / Admins"
          value={`${totalStaff} / ${totalAdmins}`}
          subtitle={`${totalStaff + totalAdmins} total`}
        />
      </div>

      {/* Branch breakdown */}
      <div className="section">
        <h3 className="section-title">
          🏢 Branch Overview
        </h3>
        <Table
          columns={branchColumns}
          data={branchList}
          emptyMessage="No branch data"
        />
      </div>

      {/* System Activity */}
      {activityLog.length > 0 && (
        <div className="section">
          <h3 className="section-title">
            📜 Recent System Activity
          </h3>
          <Table
            columns={activityColumns}
            data={activityLog}
            emptyMessage="No recent activity"
          />
        </div>
      )}
    </div>
  );
}

export default SuperAdminDashboard;
