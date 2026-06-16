import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { getSuperAdminDashboard } from "../../services/dashboardService";
import StatCard from "../../components/StatCard";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const fmt = (n) => Number(n || 0).toLocaleString();

function Row({ label, value, bold }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between",
      padding: "8px 0", borderBottom: "1px solid var(--border)",
      fontSize: 14,
    }}>
      <span className="text-muted">{label}</span>
      <span style={{ fontWeight: bold ? 700 : 500 }}>{value}</span>
    </div>
  );
}
Row.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  bold: PropTypes.bool,
};

function SuperAdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getSuperAdminDashboard());
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load CEO dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  if (loading) return <Loader message="Loading CEO dashboard..." />;
  if (error)   return <ErrorMessage message={error} onRetry={fetchDashboard} />;
  if (!data)   return <div className="empty-state">No dashboard data available.</div>;

  const branches  = data.branches  || {};
  const revenue   = data.revenue   || {};
  const top       = data.top_branch || null;
  const personnel = data.personnel || {};
  const sys       = data.system_activity || {};
  const cleaning  = sys.cleaning_today || {};

  const cleaningPct = cleaning.total
    ? Math.round((cleaning.completed / cleaning.total) * 100)
    : 0;

  return (
    <div>
      <div className="page-header"><h1>CEO Dashboard</h1></div>

      <div className="stat-grid">
        <StatCard
          title="Branches"
          value={branches.total ?? 0}
          subtitle={`${branches.active ?? 0} active`}
        />
        <StatCard
          title="Revenue This Month"
          value={`${fmt(revenue.month)} UZS`}
          subtitle={`${fmt(revenue.today)} UZS today`}
        />
        <StatCard
          title="Top Branch"
          value={top?.name || "—"}
          subtitle={top?.revenue ? `${fmt(top.revenue)} UZS this month` : undefined}
        />
        <StatCard
          title="Workforce"
          value={`${personnel.active_staff ?? 0} / ${personnel.active_admins ?? 0}`}
          subtitle="Staff / Administrators"
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
        <div className="card" style={{ margin: 0 }}>
          <h3 className="section-title" style={{ marginTop: 0 }}>Bookings</h3>
          <Row label="Today"      value={fmt(sys.bookings_today)} />
          <Row label="This month" value={fmt(sys.bookings_month)} bold />
        </div>

        <div className="card" style={{ margin: 0 }}>
          <h3 className="section-title" style={{ marginTop: 0 }}>Housekeeping Today</h3>
          <Row label="Total tasks" value={fmt(cleaning.total)} />
          <Row label="Completed"   value={`${fmt(cleaning.completed)} (${cleaningPct}%)`} />
          <Row label="Pending"     value={fmt(cleaning.pending)} />
          <Row label="Retries"     value={fmt(cleaning.retry)} bold />
        </div>
      </div>

      {sys.active_security_blocks > 0 && (
        <div className="card" style={{ marginTop: 16, borderLeft: "4px solid #ef4444" }}>
          <strong style={{ color: "#ef4444" }}>
            ⚠ {sys.active_security_blocks} active security block(s)
          </strong>{" "}
          — review the Security page.
        </div>
      )}
    </div>
  );
}

export default SuperAdminDashboard;
