import { useState, useRef } from "react";
import Button from "./Button";

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
      alert("Reason must be at least 5 characters");
      return;
    }
    onOverride(task.id, overrideReason.trim());
    setShowOverrideInput(false);
    setOverrideReason("");
  };

  return (
    <div
      style={{
        background: "#fff",
        border: `1px solid ${task.status === "retry_required" ? "#fecaca" : "#e5e7eb"}`,
        borderRadius: 8,
        padding: 16,
        marginBottom: 12,
        boxShadow: task.status === "retry_required"
          ? "0 0 0 2px rgba(239,68,68,0.15)"
          : "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: 15 }}>
            Room {task.room_number}
          </span>
          {task.branch_name && (
            <span style={{ color: "#6b7280", fontSize: 13, marginLeft: 8 }}>
              ({task.branch_name})
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              color: "#fff",
              backgroundColor: PRIORITY_COLORS[task.priority] || "#94a3b8",
              textTransform: "uppercase",
            }}
          >
            {task.priority}
          </span>
          <span
            style={{
              padding: "2px 10px",
              borderRadius: 12,
              fontSize: 12,
              fontWeight: 600,
              color: "#fff",
              backgroundColor: STATUS_COLORS[task.status] || "#6b7280",
            }}
          >
            {STATUS_LABELS[task.status] || task.status}
          </span>
        </div>
      </div>

      {/* Info */}
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 10, display: "flex", flexWrap: "wrap", gap: "4px 16px" }}>
        <span>
          <strong>Staff:</strong> {task.assigned_to_name || "Unassigned"}
        </span>
        {task.retry_count > 0 && (
          <span style={{ color: "#ef4444" }}>
            <strong>Retries:</strong> {task.retry_count}
          </span>
        )}
      </div>

      {/* Retry warning */}
      {task.status === "retry_required" && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            padding: "8px 12px",
            marginBottom: 10,
            fontSize: 13,
            color: "#991b1b",
          }}
        >
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
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 2 }}>
              Override reason (min 5 chars)
            </label>
            <input
              type="text"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Reason for overriding AI decision..."
              style={{
                width: "100%",
                padding: 6,
                border: "1px solid #dadce0",
                borderRadius: 4,
                fontSize: 13,
                boxSizing: "border-box",
              }}
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
