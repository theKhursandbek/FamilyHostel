import { useState, useEffect, useCallback } from "react";
import { getFacilityLogs, createFacilityLog, updateFacilityLog } from "../../services/directorService";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const TYPE_LABELS = { gas: "Gas", water: "Water", electricity: "Electricity", repair: "Repair" };
const STATUS_COLORS = { open: "#f59e0b", resolved: "#22c55e" };

function FacilityLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [togglingId, setTogglingId] = useState(null);
  const [form, setForm] = useState({ type: "water", description: "", cost: "" });

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getFacilityLogs();
      setLogs(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.description.trim()) return alert("Description is required");
    setCreating(true);
    try {
      const payload = { type: form.type, description: form.description };
      if (form.cost) payload.cost = form.cost;
      await createFacilityLog(payload);
      setModalOpen(false);
      setForm({ type: "water", description: "", cost: "" });
      fetchLogs();
    } catch (err) {
      const detail = err.response?.data;
      alert(typeof detail === "string" ? detail : detail?.detail || "Failed to create log");
    } finally {
      setCreating(false);
    }
  };

  const toggleStatus = async (log) => {
    const newStatus = log.status === "open" ? "resolved" : "open";
    setTogglingId(log.id);
    try {
      await updateFacilityLog(log.id, { status: newStatus });
      fetchLogs();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to update status");
    } finally {
      setTogglingId(null);
    }
  };

  const columns = [
    { key: "type", label: "Type", render: (val) => TYPE_LABELS[val] || val },
    {
      key: "description",
      label: "Description",
      render: (val) => (
        <span style={{ maxWidth: 300, display: "inline-block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {val}
        </span>
      ),
    },
    {
      key: "cost",
      label: "Cost",
      render: (val) => (val === null || val === undefined || val === "0.00" ? "—" : `${Number(val).toLocaleString()} сум`),
    },
    {
      key: "status",
      label: "Status",
      render: (val) => (
        <span
          style={{
            padding: "2px 10px",
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
            color: "#fff",
            backgroundColor: STATUS_COLORS[val] || "#6b7280",
            textTransform: "capitalize",
          }}
        >
          {val}
        </span>
      ),
    },
    {
      key: "created_at",
      label: "Date",
      render: (val) => (val ? new Date(val).toLocaleDateString() : "—"),
    },
    {
      key: "_actions",
      label: "",
      render: (_, row) => (
        <Button
          variant={row.status === "open" ? "secondary" : "ghost"}
          size="sm"
          disabled={togglingId === row.id}
          onClick={(e) => { e.stopPropagation(); toggleStatus(row); }}
        >
          {togglingId === row.id ? "…" : row.status === "open" ? "Resolve" : "Re-open"}
        </Button>
      ),
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchLogs} />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>Facility Logs</h1>
        <Button onClick={() => setModalOpen(true)}>+ New Log</Button>
      </div>

      <Table columns={columns} data={logs} emptyMessage="No facility logs" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="New Facility Log">
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Type *</label>
            <select
              value={form.type}
              onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}
              style={{ width: "100%", padding: 8, border: "1px solid #dadce0", borderRadius: 4, fontSize: 14, boxSizing: "border-box" }}
            >
              <option value="gas">Gas</option>
              <option value="water">Water</option>
              <option value="electricity">Electricity</option>
              <option value="repair">Repair</option>
            </select>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Description *</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              placeholder="Describe the issue..."
              rows={3}
              style={{ width: "100%", padding: 8, border: "1px solid #dadce0", borderRadius: 4, fontSize: 14, boxSizing: "border-box", resize: "vertical" }}
            />
          </div>

          <Input label="Cost (optional)" type="number" value={form.cost} onChange={(e) => setForm((p) => ({ ...p, cost: e.target.value }))} min="0" step="1000" />

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
            <Button type="submit" disabled={creating}>{creating ? "Saving..." : "Create Log"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default FacilityLogsPage;
