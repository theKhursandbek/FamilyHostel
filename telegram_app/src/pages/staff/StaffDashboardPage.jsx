import { useEffect, useState, useCallback } from "react";
import {
  listMyTasks,
  listMyDaysOff,
  listMyPenalties,
} from "../../services/resources";
import { Loader, ErrorBox, Empty } from "../../components/Status";
import { useAuth } from "../../context/AuthContext";

const TASK_BADGE = {
  pending: "badge-warning",
  in_progress: "badge-info",
  completed: "badge-success",
  retry_required: "badge-danger",
};

/**
 * Personal staff dashboard inside the Telegram Mini App.
 *
 * Shows a digest:
 *   - active cleaning tasks
 *   - upcoming days off
 *   - recent penalties
 *
 * Each section degrades gracefully if its endpoint is unavailable for the
 * current account — empty + a hint, never a hard failure.
 */
function StaffDashboardPage() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [daysOff, setDaysOff] = useState([]);
  const [penalties, setPenalties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, d, p] = await Promise.allSettled([
        listMyTasks(),
        listMyDaysOff(),
        listMyPenalties(),
      ]);
      setTasks(t.status === "fulfilled" ? t.value : []);
      setDaysOff(d.status === "fulfilled" ? d.value : []);
      setPenalties(p.status === "fulfilled" ? p.value : []);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't load your dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={fetchAll} />;

  const activeTasks = tasks.filter(
    (t) => t.status !== "completed" && t.status !== "cancelled"
  );

  return (
    <div>
      <h1>Staff Dashboard</h1>
      <p className="text-hint">
        Hi {user?.telegram_id ? `#${user.telegram_id}` : "there"}, here's your day.
      </p>

      {/* Quick stats */}
      <div style={{ display: "flex", gap: 8, marginTop: 12, marginBottom: 16 }}>
        <Stat label="Active tasks" value={activeTasks.length} />
        <Stat label="Days off" value={daysOff.length} />
        <Stat label="Penalties" value={penalties.length} />
      </div>

      <h2>🧹 My Cleaning Tasks</h2>
      {activeTasks.length === 0 ? (
        <Empty>No active tasks. Nice work! ✨</Empty>
      ) : (
        activeTasks.map((task) => (
          <div key={task.id} className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div className="card-title">
                  Room {task.room_number || `#${task.room}`}
                </div>
                <div className="card-subtitle">
                  {task.priority ? `Priority: ${task.priority}` : "Normal priority"}
                </div>
              </div>
              <span className={`badge ${TASK_BADGE[task.status] || "badge-muted"}`}>
                {task.status?.replace("_", " ")}
              </span>
            </div>
          </div>
        ))
      )}

      <h2 style={{ marginTop: 24 }}>📅 Days Off</h2>
      {daysOff.length === 0 ? (
        <Empty>No upcoming days off requested.</Empty>
      ) : (
        daysOff.slice(0, 5).map((d) => (
          <div key={d.id} className="card">
            <div className="card-title">
              {d.date || `${d.start_date} → ${d.end_date}`}
            </div>
            <div className="card-subtitle">
              {d.status || "Pending"}
              {d.reason ? ` · ${d.reason}` : ""}
            </div>
          </div>
        ))
      )}

      <h2 style={{ marginTop: 24 }}>⚠️ Penalties</h2>
      {penalties.length === 0 ? (
        <Empty>No penalties on record.</Empty>
      ) : (
        penalties.slice(0, 5).map((p) => (
          <div key={p.id} className="card">
            <div className="card-title">
              {p.amount ? `${Number(p.amount).toLocaleString()} UZS` : "Penalty"}
            </div>
            <div className="card-subtitle">
              {p.reason || p.description || "—"}
              {p.created_at ? ` · ${new Date(p.created_at).toLocaleDateString()}` : ""}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div
      className="card"
      style={{ flex: 1, textAlign: "center", marginBottom: 0, padding: 12 }}
    >
      <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{value}</div>
      <div className="text-hint" style={{ fontSize: "0.75rem" }}>
        {label}
      </div>
    </div>
  );
}

export default StaffDashboardPage;
