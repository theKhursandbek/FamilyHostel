import { useState, useRef } from "react";
import PropTypes from "prop-types";
import Button from "./Button";
import { useToast } from "../context/ToastContext";

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  retry_required: "Retry Required",
};

const STATUS_TONE = {
  pending: "is-pending",
  in_progress: "is-progress",
  completed: "is-completed",
  retry_required: "is-retry",
};

const PRIORITY_LABELS = {
  low: "Low",
  normal: "Normal",
  high: "High",
};

function CleaningTaskCard({
  task,
  isStaff = false,
  isDirector,
  canManage = false,
  canOverride = false,
  onAssign,
  onComplete,
  onUpload,
  onRetry,
  onOverride,
  onViewDetail,
  onEdit,
  onDelete,
  actionLoading,
}) {
  const fileRef = useRef(null);
  const toast = useToast();
  const [overrideReason, setOverrideReason] = useState("");
  const [showOverrideInput, setShowOverrideInput] = useState(false);

  const isActionLoading = actionLoading === task.id;

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) onUpload(task.id, files);
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

  const tone = STATUS_TONE[task.status] || "is-pending";
  const isRetry = task.status === "retry_required";

  return (
    <article className={`clean-card ${tone}${isRetry ? " is-attention" : ""}`}>
      <span className="clean-card__rail" aria-hidden />

      <header className="clean-card__head">
        <div className="clean-card__title-wrap">
          <span className="clean-card__crest" aria-hidden>
            {task.room_number ?? "·"}
          </span>
          <div style={{ minWidth: 0 }}>
            <h3 className="clean-card__title">
              Housekeeping
            </h3>
            <div className="clean-card__ids">
              <span className="id-chip" title="Cleaning task ID">
                <span className="id-chip__hash">№</span>
                <span className="id-chip__num">{task.id}</span>
                <span className="id-chip__lbl">task</span>
              </span>
            </div>
          </div>
        </div>

        <span className={`clean-card__status ${tone}`}>
          {STATUS_LABELS[task.status] || task.status}
        </span>
      </header>

      <div className="clean-card__plate">
        <div className="clean-card__plate-cell">
          <span className="clean-card__plate-lbl">Priority</span>
          <span className={`prio-pill prio-${task.priority || "normal"}`}>
            {PRIORITY_LABELS[task.priority] || task.priority || "Normal"}
          </span>
        </div>
        <div className="clean-card__plate-cell">
          <span className="clean-card__plate-lbl">Assigned</span>
          <span className="clean-card__plate-val">
            {task.assigned_to_name || (
              <span className="clean-card__plate-val--muted">Unassigned</span>
            )}
          </span>
        </div>
        {task.retry_count > 0 && (
          <div className="clean-card__plate-cell">
            <span className="clean-card__plate-lbl">Retries</span>
            <span className="clean-card__plate-val clean-card__plate-val--warn">
              ×{task.retry_count}
            </span>
          </div>
        )}
      </div>

      {isRetry && (
        <div className="clean-card__alert">
          <span aria-hidden>⚠️</span>
          <span>AI rejected the result — re-clean the room and submit new photos.</span>
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      <div className="clean-card__actions">
        {/* ---- Staff-only operational buttons ---------------------------- */}
        {isStaff && task.status === "pending" && (
          <Button size="sm" disabled={isActionLoading} onClick={() => onAssign(task.id)}>
            {isActionLoading ? "…" : "Start Task"}
          </Button>
        )}

        {isStaff && (task.status === "in_progress" || task.status === "retry_required") && (
          <Button
            variant="secondary"
            size="sm"
            disabled={isActionLoading}
            onClick={() => fileRef.current?.click()}
          >
            Upload Photos
          </Button>
        )}

        {isStaff && (task.status === "in_progress" || task.status === "retry_required") && (
          <Button size="sm" disabled={isActionLoading} onClick={() => onComplete(task.id)}>
            {isActionLoading ? "…" : "Complete"}
          </Button>
        )}

        {isStaff && isRetry && (
          <Button
            variant="danger"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onRetry(task.id)}
          >
            {isActionLoading ? "…" : "Re-clean"}
          </Button>
        )}

        {/* ---- Admin / Director / SuperAdmin buttons --------------------- */}
        {/* Override is the admin's force-approve path — mutually exclusive
            with the staff Complete button (staff finishes the normal flow,
            admin overrides only when the AI / staff workflow is stuck). */}
        {!isStaff && (canOverride || isDirector) && task.status !== "completed" && task.status !== "pending" && !showOverrideInput && (
          <Button
            variant="ghost"
            size="sm"
            disabled={isActionLoading}
            onClick={() => setShowOverrideInput(true)}
          >
            Override
          </Button>
        )}

        {/* Edit is allowed on anything that isn't completed (even when a
            staff member is already assigned / working). */}
        {canManage && onEdit && task.status !== "completed" && (
          <Button
            variant="ghost"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onEdit(task)}
          >
            Edit
          </Button>
        )}

        {canManage && onDelete && task.status === "pending" && (
          <Button
            variant="danger"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onDelete(task)}
          >
            Delete
          </Button>
        )}

        <Button variant="ghost" size="sm" onClick={() => onViewDetail(task.id)}>
          Details →
        </Button>
      </div>

      {showOverrideInput && (
        <div className="clean-card__override">
          <div style={{ flex: 1 }}>
            <label htmlFor={`override-reason-${task.id}`} className="label" style={{ fontSize: 12 }}>
              Override reason (min 5 chars)
            </label>
            <input
              id={`override-reason-${task.id}`}
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
    </article>
  );
}

CleaningTaskCard.propTypes = {
  task: PropTypes.shape({
    id: PropTypes.number.isRequired,
    room: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    status: PropTypes.string.isRequired,
    room_number: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    branch_name: PropTypes.string,
    priority: PropTypes.string,
    assigned_to_name: PropTypes.string,
    retry_count: PropTypes.number,
  }).isRequired,
  isDirector: PropTypes.bool,
  isStaff: PropTypes.bool,
  canManage: PropTypes.bool,
  canOverride: PropTypes.bool,
  onAssign: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  onUpload: PropTypes.func.isRequired,
  onRetry: PropTypes.func.isRequired,
  onOverride: PropTypes.func.isRequired,
  onViewDetail: PropTypes.func.isRequired,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  actionLoading: PropTypes.number,
};

export default CleaningTaskCard;
