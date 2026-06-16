import { useState } from "react";
import PropTypes from "prop-types";
import { CheckCircle2, XCircle, Check, X } from "lucide-react";
import Modal from "./Modal";
import Lightbox from "./Lightbox";

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  ai_checking: "AI Checking…",
  completed: "Completed",
  retry_required: "Retry Required",
};

const ZONE_LABELS = {
  bed: "Bed",
  bathroom: "Bathroom",
  floor: "Floor",
  trash: "Trash & surfaces",
  extra: "Extra",
};

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span className="info-row-label">{label}</span>
      <span className="info-row-value">{value ?? "—"}</span>
    </div>
  );
}

InfoRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

function CleaningTaskDetail({ task, isOpen, onClose }) {
  const [lightboxIndex, setLightboxIndex] = useState(null);
  if (!task) return null;

  const aiResults = task.ai_results || [];
  const images = (task.images || []).filter((img) => img.image_url && !img.is_purged);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Task #${task.id} — Room ${task.room_number}`}>
      {/* Basic info */}
      <InfoRow label="Room" value={task.room_number} />
      <InfoRow label="Branch" value={task.branch_name} />
      <InfoRow label="Status" value={STATUS_LABELS[task.status] || task.status} />
      <InfoRow label="Priority" value={task.priority} />
      <InfoRow label="Assigned to" value={task.assigned_to_name || "Unassigned"} />
      <InfoRow label="Retry count" value={task.retry_count} />
      <InfoRow label="Notes" value={task.notes || "—"} />
      <InfoRow
        label="Created"
        value={task.created_at ? new Date(task.created_at).toLocaleString() : "—"}
      />
      <InfoRow
        label="Completed"
        value={task.completed_at ? new Date(task.completed_at).toLocaleString() : "—"}
      />

      {/* Zone photos */}
      <h4 className="section-title" style={{ margin: "16px 0 8px" }}>
        Photos ({images.length})
      </h4>
      {images.length === 0 ? (
        <p className="text-secondary" style={{ fontSize: 13 }}>No photos available.</p>
      ) : (
        <div className="clean-detail__zones">
          {images.map((img, i) => (
            <button
              key={img.id}
              type="button"
              className="clean-detail__zone"
              onClick={() => setLightboxIndex(i)}
            >
              <img src={img.image_url} alt={`${img.zone} zone`} className="clean-detail__zone-img" />
              <span className="clean-detail__zone-tag">{ZONE_LABELS[img.zone] || img.zone}</span>
            </button>
          ))}
        </div>
      )}

      {/* AI Results */}
      <h4 className="section-title" style={{ margin: "16px 0 8px" }}>
        AI Results ({aiResults.length})
      </h4>
      {aiResults.length === 0 ? (
        <p className="text-secondary" style={{ fontSize: 13 }}>No AI analysis results.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {aiResults.map((result) => (
            <div
              key={result.id}
              className="card"
              style={{
                borderColor: result.result === "approved"
                  ? "var(--text-success, #22c55e)"
                  : "var(--danger, #ef4444)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <strong
                  className={result.result === "approved" ? "text-success" : "text-accent"}
                  style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                >
                  {result.result === "approved" ? (
                    <><CheckCircle2 size={15} strokeWidth={2} /> Approved</>
                  ) : (
                    <><XCircle size={15} strokeWidth={2} /> Rejected</>
                  )}
                </strong>
                <span className="text-secondary" style={{ fontSize: 12 }}>
                  {result.created_at ? new Date(result.created_at).toLocaleString() : ""}
                </span>
              </div>
              {result.feedback_text && (
                <p style={{ margin: 0, color: "var(--text)" }}>{result.feedback_text}</p>
              )}
              {Array.isArray(result.zones) && result.zones.length > 0 && (
                <ul className="clean-detail__ai-zones">
                  {result.zones.map((z) => (
                    <li key={z.zone} className={z.clean ? "is-clean" : "is-dirty"}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 5, textTransform: "capitalize" }}>
                        {z.clean ? <Check size={13} strokeWidth={2.6} /> : <X size={13} strokeWidth={2.6} />} {z.zone}
                      </span>
                      {!z.clean && (z.issues || []).length > 0 && (
                        <span className="clean-detail__ai-issues"> — {z.issues.join(", ")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {result.failure_reason && (
                <p className="text-secondary" style={{ margin: "4px 0 0", fontSize: 12 }}>
                  Verification could not run ({result.failure_reason}).
                </p>
              )}
              {result.ai_model_version && (
                <p className="text-secondary" style={{ margin: "4px 0 0", fontSize: 12 }}>
                  Model: {result.ai_model_version}
                  {result.confidence != null && ` · confidence ${Math.round(result.confidence * 100)}%`}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {lightboxIndex !== null && (
        <Lightbox
          images={images.map((img) => ({ id: img.id, url: img.image_url, alt: img.zone }))}
          startIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </Modal>
  );
}

CleaningTaskDetail.propTypes = {
  task: PropTypes.object,
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

export default CleaningTaskDetail;
