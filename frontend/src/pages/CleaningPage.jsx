import { useState, useEffect, useCallback } from "react";
import {
  getTasks,
  getTask,
  assignTask,
  completeTask,
  uploadImages,
  retryTask,
  overrideTask,
} from "../services/cleaningService";
import { useAuth } from "../context/AuthContext";
import { useSocket } from "../hooks/useSocket";
import CleaningTaskCard from "../components/CleaningTaskCard";
import CleaningTaskDetail from "../components/CleaningTaskDetail";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In Progress" },
  { value: "retry_required", label: "Retry Required" },
  { value: "completed", label: "Completed" },
];

function CleaningPage() {
  const { user } = useAuth();
  const isDirector = user?.roles?.includes("director") ?? false;

  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");

  // Detail modal
  const [detailTask, setDetailTask] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      const data = await getTasks(params);
      setTasks(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load cleaning tasks");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Real-time updates via WebSocket
  const wsChannel = isDirector ? "director" : "admin";
  useSocket(wsChannel, {
    cleaning_task_updated: () => fetchTasks(),
  });

  const withAction = async (taskId, action) => {
    setActionLoading(taskId);
    try {
      await action();
      fetchTasks();
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.detail || detail?.reason?.[0] || "Action failed";
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAssign = (taskId) => withAction(taskId, () => assignTask(taskId));
  const handleComplete = (taskId) => withAction(taskId, () => completeTask(taskId));
  const handleRetry = (taskId) => withAction(taskId, () => retryTask(taskId));

  const handleUpload = (taskId, files) =>
    withAction(taskId, () => uploadImages(taskId, files));

  const handleOverride = (taskId, reason) =>
    withAction(taskId, () => overrideTask(taskId, reason));

  const handleViewDetail = async (taskId) => {
    setDetailLoading(true);
    setDetailOpen(true);
    try {
      const data = await getTask(taskId);
      setDetailTask(data);
    } catch {
      setDetailTask(null);
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchTasks} />;

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <h1 style={{ margin: 0 }}>Cleaning Tasks</h1>

        {/* Status filter */}
        <div style={{ display: "flex", gap: 4 }}>
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              style={{
                padding: "4px 12px",
                borderRadius: 14,
                border: "1px solid #dadce0",
                background: statusFilter === f.value ? "#1a73e8" : "#fff",
                color: statusFilter === f.value ? "#fff" : "#5f6368",
                fontSize: 13,
                fontWeight: statusFilter === f.value ? 600 : 400,
                cursor: "pointer",
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Task count */}
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "#6b7280" }}>
        {tasks.length} task{tasks.length === 1 ? "" : "s"}
      </p>

      {/* Task list */}
      {tasks.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "#9ca3af" }}>
          No cleaning tasks found.
        </div>
      ) : (
        tasks.map((task) => (
          <CleaningTaskCard
            key={task.id}
            task={task}
            isDirector={isDirector}
            actionLoading={actionLoading}
            onAssign={handleAssign}
            onComplete={handleComplete}
            onUpload={handleUpload}
            onRetry={handleRetry}
            onOverride={handleOverride}
            onViewDetail={handleViewDetail}
          />
        ))
      )}

      {/* Detail modal */}
      <CleaningTaskDetail
        task={detailTask}
        isOpen={detailOpen}
        onClose={() => {
          setDetailOpen(false);
          setDetailTask(null);
        }}
      />
      {detailOpen && detailLoading && (
        <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 1001 }}>
          <Loader />
        </div>
      )}
    </div>
  );
}

export default CleaningPage;
