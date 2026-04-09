import Modal from "./Modal";

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  retry_required: "Retry Required",
};

function InfoRow({ label, value }) {
  return (
    <div style={{ display: "flex", padding: "6px 0", borderBottom: "1px solid #f3f4f6" }}>
      <span style={{ width: 140, fontWeight: 500, color: "#6b7280", fontSize: 13, flexShrink: 0 }}>{label}</span>
      <span style={{ color: "#1f2937", fontSize: 13 }}>{value ?? "—"}</span>
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
      <h4 style={{ margin: "16px 0 8px", fontSize: 14, color: "#374151" }}>
        Photos ({images.length})
      </h4>
      {images.length === 0 ? (
        <p style={{ fontSize: 13, color: "#9ca3af" }}>No photos uploaded yet.</p>
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
                  border: "1px solid #e5e7eb",
                }}
              />
            </a>
          ))}
        </div>
      )}

      {/* AI Results */}
      <h4 style={{ margin: "16px 0 8px", fontSize: 14, color: "#374151" }}>
        AI Results ({aiResults.length})
      </h4>
      {aiResults.length === 0 ? (
        <p style={{ fontSize: 13, color: "#9ca3af" }}>No AI analysis results.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {aiResults.map((result) => (
            <div
              key={result.id}
              style={{
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
                border: `1px solid ${result.result === "approved" ? "#bbf7d0" : "#fecaca"}`,
                background: result.result === "approved" ? "#f0fdf4" : "#fef2f2",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <strong style={{ color: result.result === "approved" ? "#16a34a" : "#dc2626" }}>
                  {result.result === "approved" ? "✅ Approved" : "❌ Rejected"}
                </strong>
                <span style={{ fontSize: 12, color: "#9ca3af" }}>
                  {result.analyzed_at ? new Date(result.analyzed_at).toLocaleString() : ""}
                </span>
              </div>
              {result.notes && (
                <p style={{ margin: 0, color: "#374151" }}>{result.notes}</p>
              )}
              {result.model_version && (
                <p style={{ margin: "4px 0 0", color: "#9ca3af", fontSize: 12 }}>
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
