import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getTasks } from "../../services/cleaningService";
import { getDayOffRequests, getMyPenalties } from "../../services/staffService";
import { useSocket } from "../../hooks/useSocket";
import StatCard from "../../components/StatCard";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

/**
 * Personal dashboard for Staff users.
 *
 * Pulls together the three things a cleaner / receptionist needs at a glance:
 *  - Active cleaning tasks assigned to them
 *  - Pending day-off requests
 *  - Open penalties (unpaid)
 *
 * No data == friendly empty states (not zeros that look like a broken page).
 */
const TASK_BADGE = {
  pending: "badge-warning",
  in_progress: "badge-info",
  completed: "badge-success",
  retry_required: "badge-danger",
};

const taskColumns = [
  { key: "room_number", label: "Room", render: (val, row) => val || row.room?.number || "—" },
  {
    key: "status",
    label: "Status",
    render: (val) => (
      <span className={`badge ${TASK_BADGE[val] || "badge-muted"}`} style={{ textTransform: "capitalize" }}>
        {(val || "—").replace("_", " ")}
      </span>
    ),
  },
  {
    key: "scheduled_for",
    label: "Scheduled",
    render: (val) => (val ? new Date(val).toLocaleString() : "—"),
  },
];

const DAYOFF_BADGE = {
  pending: "badge-warning",
  approved: "badge-success",
  rejected: "badge-danger",
};

const dayOffColumns = [
  { key: "start_date", label: "Start" },
  { key: "end_date", label: "End" },
  { key: "reason", label: "Reason", render: (val) => val || "—" },
  {
    key: "status",
    label: "Status",
    render: (val) => (
      <span
        className={`badge ${DAYOFF_BADGE[val] || "badge-muted"}`}
        style={{ textTransform: "capitalize" }}
      >
        {val}
      </span>
    ),
  },
];

const penaltyColumns = [
  { key: "reason", label: "Reason", render: (val) => val || "—" },
  {
    key: "amount",
    label: "Amount",
    render: (val) => `${Number(val || 0).toLocaleString()} UZS`,
  },
  {
    key: "is_paid",
    label: "Status",
    render: (val) => (
      <span className={`badge ${val ? "badge-success" : "badge-danger"}`}>
        {val ? "Paid" : "Unpaid"}
      </span>
    ),
  },
  {
    key: "created_at",
    label: "Issued",
    render: (val) => (val ? new Date(val).toLocaleDateString() : "—"),
  },
];

function asArray(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function StaffDashboard() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [daysOff, setDaysOff] = useState([]);
  const [penalties, setPenalties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [taskRes, daysOffRes, penaltiesRes] = await Promise.allSettled([
        getTasks({ assigned_to_me: true }),
        getDayOffRequests(),
        getMyPenalties(),
      ]);
      if (taskRes.status === "fulfilled") setTasks(asArray(taskRes.value));
      if (daysOffRes.status === "fulfilled") setDaysOff(asArray(daysOffRes.value));
      if (penaltiesRes.status === "fulfilled") setPenalties(asArray(penaltiesRes.value));

      // Surface any failure if EVERY request failed
      const allFailed =
        taskRes.status === "rejected" &&
        daysOffRes.status === "rejected" &&
        penaltiesRes.status === "rejected";
      if (allFailed) {
        setError(taskRes.reason?.response?.data?.detail || "Failed to load dashboard.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Live refresh when the cleaning task assigned to me changes
  useSocket("staff", {
    cleaning_task_updated: () => fetchAll(),
    penalty_created: () => fetchAll(),
    day_off_request_updated: () => fetchAll(),
  });

  if (loading) return <Loader message="Loading your dashboard..." />;
  if (error) return <ErrorMessage message={error} onRetry={fetchAll} />;

  const activeTasks = tasks.filter((t) => t.status !== "completed");
  const pendingDaysOff = daysOff.filter((r) => r.status === "pending");
  const unpaidPenalties = penalties.filter((p) => !p.is_paid);
  const unpaidTotal = unpaidPenalties.reduce((sum, p) => sum + Number(p.amount || 0), 0);

  return (
    <div>
      <div className="page-header">
        <h1>Welcome{user?.phone ? `, ${user.phone}` : ""}</h1>
      </div>

      <div className="stat-grid">
        <StatCard
          title="Active Tasks"
          value={activeTasks.length}
          subtitle={`${tasks.length} total`}
        />
        <StatCard
          title="Day-Off Requests"
          value={pendingDaysOff.length}
          subtitle="pending approval"
        />
        <StatCard
          title="Unpaid Penalties"
          value={unpaidPenalties.length}
          subtitle={`${unpaidTotal.toLocaleString()} UZS`}
        />
        <StatCard
          title="Quick Action"
          value={<Link to="/staff/days-off" style={{ color: "#60a5fa" }}>Request Day Off →</Link>}
        />
      </div>

      <div className="section">
        <h3 className="section-title">My Active Tasks</h3>
        <Table
          columns={taskColumns}
          data={activeTasks}
          emptyMessage="No active tasks — you're all caught up!"
        />
        {tasks.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <Link to="/staff/my-tasks" style={{ fontSize: 13 }}>View all →</Link>
          </div>
        )}
      </div>

      <div className="section">
        <h3 className="section-title">My Day-Off Requests</h3>
        <Table
          columns={dayOffColumns}
          data={daysOff.slice(0, 5)}
          emptyMessage="No day-off requests yet."
        />
      </div>

      <div className="section">
        <h3 className="section-title">My Penalties</h3>
        <Table
          columns={penaltyColumns}
          data={penalties.slice(0, 5)}
          emptyMessage="No penalties — keep it up!"
        />
      </div>
    </div>
  );
}

export default StaffDashboard;
