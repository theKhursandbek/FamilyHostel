import { useState, useRef } from "react";
import Button from "./Button";
import { useToast } from "../context/ToastContext";

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  retry_required: "Retry Required",
};

const STATUS_COLORS = {
  pending: "#f59e0b",
  in_progress: "#3b82f6",
  completed: "#22c55e",
  retry_required: "#ef4444",
};

const PRIORITY_COLORS = {
  low: "#94a3b8",
  normal: "#3b82f6",
  high: "#ef4444",
};

function CleaningTaskCard({
  task,
  isDirector,
  onAssign,
  onComplete,
  onUpload,
  onRetry,
  onOverride,
  onViewDetail,
  actionLoading,
}) {
  const fileRef = useRef(null);
  const toast = useToast();
  const [overrideReason, setOverrideReason] = useState("");
  const [showOverrideInput, setShowOverrideInput] = useState(false);

  const isActionLoading = actionLoading === task.id;

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      onUpload(task.id, files);
    }
    e.target.value = "";
  };

  const handleOverrideSubmit = () => {
    if (overrideReason.trim().length < 5) {
      toast.warning("Reason must be at least 5 characters");
      return;
    }
    onOverride(task.id, overrideReason.trim());
    setShowOverrideInput(false);
    setOverrideReason("");
  };

  return (
    <div className={`task-card${task.status === "retry_required" ? " retry" : ""}`}>
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: 15 }}>
            Room {task.room_number}
          </span>
          {task.branch_name && (
            <span className="text-muted" style={{ fontSize: 13, marginLeft: 8 }}>
              ({task.branch_name})
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span
            className="badge badge-sm"
            style={{ backgroundColor: PRIORITY_COLORS[task.priority] || "#94a3b8" }}
          >
            {task.priority}
          </span>
          <span
            className="badge"
            style={{ backgroundColor: STATUS_COLORS[task.status] || "#6b7280" }}
          >
            {STATUS_LABELS[task.status] || task.status}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="text-muted" style={{ fontSize: 13, marginBottom: 10, display: "flex", flexWrap: "wrap", gap: "4px 16px" }}>
        <span>
          <strong>Staff:</strong> {task.assigned_to_name || "Unassigned"}
        </span>
        {task.retry_count > 0 && (
          <span className="text-accent">
            <strong>Retries:</strong> {task.retry_count}
          </span>
        )}
      </div>

      {/* Retry warning */}
      {task.status === "retry_required" && (
        <div className="alert alert-error">
          ⚠️ AI rejected cleaning result. Task needs re-cleaning and new photo submission.
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      {/* Actions */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {/* Assign — when pending */}
        {task.status === "pending" && (
          <Button
            size="sm"
            disabled={isActionLoading}
            onClick={() => onAssign(task.id)}
          >
            {isActionLoading ? "…" : "Start Task"}
          </Button>
        )}

        {/* Upload — when in_progress or retry_required */}
        {(task.status === "in_progress" || task.status === "retry_required") && (
          <Button
            variant="secondary"
            size="sm"
            disabled={isActionLoading}
            onClick={() => fileRef.current?.click()}
          >
            📷 Upload Photos
          </Button>
        )}

        {/* Complete — when in_progress or retry_required */}
        {(task.status === "in_progress" || task.status === "retry_required") && (
          <Button
            size="sm"
            disabled={isActionLoading}
            onClick={() => onComplete(task.id)}
          >
            {isActionLoading ? "…" : "Complete"}
          </Button>
        )}

        {/* Retry — when retry_required */}
        {task.status === "retry_required" && (
          <Button
            variant="danger"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onRetry(task.id)}
          >
            {isActionLoading ? "…" : "Re-clean"}
          </Button>
        )}

        {/* Director Override — any non-completed status */}
        {isDirector && task.status !== "completed" && !showOverrideInput && (
          <Button
            variant="ghost"
            size="sm"
            disabled={isActionLoading}
            onClick={() => setShowOverrideInput(true)}
          >
            🔓 Override
          </Button>
        )}

        {/* View Detail */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onViewDetail(task.id)}
        >
          Details →
        </Button>
      </div>

      {/* Override reason input */}
      {showOverrideInput && (
        <div style={{ marginTop: 10, display: "flex", gap: 8, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label className="label" style={{ fontSize: 12 }}>
              Override reason (min 5 chars)
            </label>
            <input
              type="text"
              className="input"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Reason for overriding AI decision..."
            />
          </div>
          <Button size="sm" disabled={isActionLoading} onClick={handleOverrideSubmit}>
            Confirm
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowOverrideInput(false);
              setOverrideReason("");
            }}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}

export default CleaningTaskCard;
