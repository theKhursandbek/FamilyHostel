import { useState, useEffect, useCallback } from "react";
import {
  getTasks,
  getTask,
  assignTask,
  completeTask,
  uploadImages,
  retryTask,
  overrideTask,
  createTask,
  updateTask,
  deleteTask,
} from "../services/cleaningService";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useSocket } from "../hooks/useSocket";
import usePersistedBranch from "../hooks/usePersistedBranch";
import CleaningTaskCard from "../components/CleaningTaskCard";
import CleaningTaskDetail from "../components/CleaningTaskDetail";
import CleaningTaskForm from "../components/CleaningTaskForm";
import BranchSelector from "../components/BranchSelector";
import Button from "../components/Button";
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
  const toast = useToast();

  const roles = user?.roles ?? [];
  const isDirector = roles.includes("director");
  const isSuperAdmin = roles.includes("superadmin");
  const isAdmin = roles.includes("administrator") || roles.includes("admin");
  const isStaff = roles.includes("staff");
  // Admin / Director / SuperAdmin can fully manage (CRUD) and override AI
  const canManage = isAdmin || isDirector || isSuperAdmin;

  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  // Branch scope. SuperAdmin must pick one; others auto-pinned by BranchSelector.
  const [branchId, setBranchId] = usePersistedBranch(
    "branchScope:cleaning",
    isSuperAdmin,
    user?.branch_id ?? null,
  );

  // Detail modal
  const [detailTask, setDetailTask] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  // Create/Edit form modal
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState("create");
  const [formTask, setFormTask] = useState(null);
  const [formSubmitting, setFormSubmitting] = useState(false);

  const fetchTasks = useCallback(async () => {
    // CEO (SuperAdmin) must pick a branch first; until then show empty state.
    if (isSuperAdmin && !branchId) {
      setTasks([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (branchId) params.branch = branchId;
      const data = await getTasks(params);
      setTasks(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load cleaning tasks");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, branchId, isSuperAdmin]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Real-time updates via WebSocket
  const wsChannel = isDirector ? "director" : "admin";
  useSocket(wsChannel, {
    cleaning_task_updated: () => fetchTasks(),
  });

  const withAction = async (taskId, action, successMsg = "Task updated") => {
    setActionLoading(taskId);
    try {
      await action();
      toast.success(successMsg);
      fetchTasks();
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.detail || detail?.reason?.[0] || "Action failed";
      toast.error(msg);
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
      setDetailOpen(false);
      toast.error("Failed to load task details");
    } finally {
      setDetailLoading(false);
    }
  };

  // ---- CRUD handlers (admin / director / superadmin only) -----------------

  const openCreate = () => {
    setFormMode("create");
    setFormTask(null);
    setFormOpen(true);
  };

  const openEdit = (task) => {
    setFormMode("edit");
    setFormTask(task);
    setFormOpen(true);
  };

  const closeForm = () => {
    if (formSubmitting) return;
    setFormOpen(false);
    setFormTask(null);
  };

  const handleFormSubmit = async (payload) => {
    setFormSubmitting(true);
    try {
      if (formMode === "create") {
        await createTask(payload);
        toast.success("Cleaning task created");
      } else if (formTask) {
        await updateTask(formTask.id, payload);
        toast.success("Task updated");
      }
      setFormOpen(false);
      setFormTask(null);
      fetchTasks();
    } catch (err) {
      const detail = err.response?.data;
      let msg = "Failed to save task";
      if (typeof detail === "string") {
        msg = detail;
      } else if (detail?.detail) {
        msg = detail.detail;
      } else if (detail && typeof detail === "object") {
        const flat = Object.values(detail).flat().join(" ");
        if (flat) msg = flat;
      }
      toast.error(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleDelete = (task) => {
    const confirmed = globalThis.confirm(
      `Delete cleaning task #${task.id} for Room ${task.room_number}?\nThis action cannot be undone.`,
    );
    if (!confirmed) return;
    withAction(task.id, () => deleteTask(task.id), "Task deleted");
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchTasks} />;

  const ceoMustPick = isSuperAdmin && !branchId;

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <h1>Cleaning Tasks</h1>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <BranchSelector value={branchId} onChange={setBranchId} />

          {/* Status filter */}
          <div style={{ display: "flex", gap: 4 }}>
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`filter-chip${statusFilter === f.value ? " active" : ""}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {canManage && !ceoMustPick && (
            <Button size="sm" onClick={openCreate}>
              + New Task
            </Button>
          )}
        </div>
      </div>

      {ceoMustPick ? (
        <div className="branch-empty">
          <p className="branch-empty__title">Select a branch to begin</p>
          <p className="branch-empty__hint">
            As CEO you oversee every branch. Pick one above to view and manage its housekeeping.
          </p>
        </div>
      ) : (
        <>
          {/* Task count */}
          <p className="text-muted" style={{ margin: "0 0 12px", fontSize: 13 }}>
            {tasks.length} task{tasks.length === 1 ? "" : "s"}
          </p>

          {/* Task list */}
          {tasks.length === 0 ? (
            <div className="empty-state">
              No cleaning tasks found.
            </div>
          ) : (
            <div className="clean-grid">
              {tasks.map((task) => (
                <CleaningTaskCard
                  key={task.id}
                  task={task}
                  isStaff={isStaff}
                  isDirector={isDirector}
                  canManage={canManage}
                  canOverride={canManage}
                  actionLoading={actionLoading}
                  onAssign={handleAssign}
                  onComplete={handleComplete}
                  onUpload={handleUpload}
                  onRetry={handleRetry}
                  onOverride={handleOverride}
                  onViewDetail={handleViewDetail}
                  onEdit={openEdit}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </>
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

      {/* Create / Edit form */}
      {canManage && (
        <CleaningTaskForm
          isOpen={formOpen}
          onClose={closeForm}
          mode={formMode}
          task={formTask}
          branchId={branchId}
          onSubmit={handleFormSubmit}
          submitting={formSubmitting}
        />
      )}
    </div>
  );
}

export default CleaningPage;
