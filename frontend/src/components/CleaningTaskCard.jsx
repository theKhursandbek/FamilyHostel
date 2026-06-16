import { useState } from "react";
import PropTypes from "prop-types";
import { AlertTriangle } from "lucide-react";
import Button from "./Button";
import CameraCapture from "./CameraCapture";

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  ai_checking: "AI Checking…",
  completed: "Completed",
  retry_required: "Retry Required",
};

const STATUS_TONE = {
  pending: "is-pending",
  in_progress: "is-progress",
  ai_checking: "is-checking",
  completed: "is-completed",
  retry_required: "is-retry",
};

const PRIORITY_LABELS = {
  low: "Low",
  normal: "Normal",
  high: "High",
};

/** Pull the latest AI result's per-zone issues for retry feedback. */
function latestRejectionFeedback(task) {
  const results = task.ai_results || [];
  if (results.length === 0) return null;
  const latest = results[0];
  if (latest.result !== "rejected") return null;
  const dirtyZones = (latest.zones || []).filter((z) => z?.clean === false);
  return { summary: latest.feedback_text || "", zones: dirtyZones };
}

function CleaningTaskCard({
  task,
  isStaff = false,
  isDirector,
  canManage = false,
  canOverride = false,
  onAssign,
  onUpload,
  onRetry,
  onOverride,
  onViewDetail,
  onEdit,
  onDelete,
  actionLoading,
}) {
  const [overrideReason, setOverrideReason] = useState("");
  const [showOverrideInput, setShowOverrideInput] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);

  const isActionLoading = actionLoading === task.id;

  const handleCameraSubmit = (items) => {
    onUpload(task.id, items);
    setCameraOpen(false);
  };

  const handleOverrideSubmit = () => {
    // Reason is OPTIONAL for "Mark Cleaned".
    onOverride(task.id, overrideReason.trim());
    setShowOverrideInput(false);
    setOverrideReason("");
  };

  const tone = STATUS_TONE[task.status] || "is-pending";
  const isRetry = task.status === "retry_required";
  const isChecking = task.status === "ai_checking";
  const rejection = isRetry ? latestRejectionFeedback(task) : null;

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
          <span aria-hidden><AlertTriangle size={16} strokeWidth={2} /></span>
          <div className="clean-card__alert-body">
            <span>{rejection?.summary || "AI rejected the result — re-clean the room and submit new photos."}</span>
            {rejection?.zones?.length > 0 && (
              <ul className="clean-card__alert-zones">
                {rejection.zones.map((z) => (
                  <li key={z.zone}>
                    <strong style={{ textTransform: "capitalize" }}>{z.zone}:</strong>{" "}
                    {(z.issues || []).join(", ") || "needs attention"}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {isChecking && (
        <div className="clean-card__checking">
          <span className="clean-card__spinner" aria-hidden />
          <span>AI is verifying your photos…</span>
        </div>
      )}

      <CameraCapture
        isOpen={cameraOpen}
        onClose={() => setCameraOpen(false)}
        onSubmit={handleCameraSubmit}
        submitting={isActionLoading}
      />

      <div className="clean-card__actions">
        {/* ---- Staff-only operational buttons ---------------------------- */}
        {isStaff && task.status === "pending" && (
          <Button size="sm" disabled={isActionLoading} onClick={() => onAssign(task.id)}>
            {isActionLoading ? "…" : "Start Task"}
          </Button>
        )}

        {/* Camera-only submission. No file picker, no staff "Complete":
            AI approval is the only staff path to done (anti-cheat). */}
        {isStaff && (task.status === "in_progress" || task.status === "retry_required") && (
          <Button
            size="sm"
            disabled={isActionLoading}
            onClick={() => setCameraOpen(true)}
          >
            📷 Clean Room
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
        {/* "Mark Cleaned" is the supervisor force-complete path (reason
            optional), available even over a negative AI verdict. */}
        {!isStaff && (canOverride || isDirector || canManage) && task.status !== "completed" && task.status !== "pending" && !showOverrideInput && (
          <Button
            variant="secondary"
            size="sm"
            disabled={isActionLoading}
            onClick={() => setShowOverrideInput(true)}
          >
            Mark Cleaned
          </Button>
        )}

        {/* Edit is allowed on anything that isn't completed (even when a
            staff member is already assigned / working). */}
        {canManage && onEdit && task.status !== "completed" && (
          <Button
            variant="secondary"
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

        <Button variant="secondary" size="sm" onClick={() => onViewDetail(task.id)}>
          Details →
        </Button>
      </div>

      {showOverrideInput && (
        <div className="clean-card__override">
          <div style={{ flex: 1 }}>
            <label htmlFor={`override-reason-${task.id}`} className="label" style={{ fontSize: 12 }}>
              Note (optional)
            </label>
            <input
              id={`override-reason-${task.id}`}
              type="text"
              className="input"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Optional reason for marking cleaned…"
            />
          </div>
          <Button size="sm" disabled={isActionLoading} onClick={handleOverrideSubmit}>
            Confirm
          </Button>
          <Button
            variant="secondary"
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
    ai_results: PropTypes.array,
  }).isRequired,
  isDirector: PropTypes.bool,
  isStaff: PropTypes.bool,
  canManage: PropTypes.bool,
  canOverride: PropTypes.bool,
  onAssign: PropTypes.func.isRequired,
  onUpload: PropTypes.func.isRequired,
  onRetry: PropTypes.func.isRequired,
  onOverride: PropTypes.func.isRequired,
  onViewDetail: PropTypes.func.isRequired,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  actionLoading: PropTypes.number,
};

export default CleaningTaskCard;
