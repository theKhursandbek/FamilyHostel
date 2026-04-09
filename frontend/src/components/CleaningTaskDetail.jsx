import Modal from "./Modal";

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  retry_required: "Retry Required",
};

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span className="info-row-label">{label}</span>
      <span className="info-row-value">{value ?? "—"}</span>
    </div>
  );
}

function CleaningTaskDetail({ task, isOpen, onClose }) {
  if (!task) return null;

  const aiResults = task.ai_results || [];
  const images = task.images || [];

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

      {/* Images */}
      <h4 className="section-title" style={{ margin: "16px 0 8px" }}>
        Photos ({images.length})
      </h4>
      {images.length === 0 ? (
        <p className="text-secondary" style={{ fontSize: 13 }}>No photos uploaded yet.</p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {images.map((img) => (
            <a
              key={img.id}
              href={img.image_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: "block" }}
            >
              <img
                src={img.image_url}
                alt={`Cleaning photo ${img.id}`}
                style={{
                  width: 100,
                  height: 100,
                  objectFit: "cover",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                }}
              />
            </a>
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
                <strong className={result.result === "approved" ? "text-success" : "text-accent"}>
                  {result.result === "approved" ? "✅ Approved" : "❌ Rejected"}
                </strong>
                <span className="text-secondary" style={{ fontSize: 12 }}>
                  {result.analyzed_at ? new Date(result.analyzed_at).toLocaleString() : ""}
                </span>
              </div>
              {result.notes && (
                <p style={{ margin: 0, color: "var(--text)" }}>{result.notes}</p>
              )}
              {result.model_version && (
                <p className="text-secondary" style={{ margin: "4px 0 0", fontSize: 12 }}>
                  Model: {result.model_version}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

export default CleaningTaskDetail;
