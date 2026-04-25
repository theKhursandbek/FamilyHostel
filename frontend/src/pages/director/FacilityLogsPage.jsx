import { useState, useEffect, useCallback } from "react";
import { getFacilityLogs, createFacilityLog, updateFacilityLog } from "../../services/directorService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Select from "../../components/Select";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const TYPE_LABELS = { gas: "Gas", water: "Water", electricity: "Electricity", repair: "Repair" };
const BADGE_MAP = { open: "badge-warning", resolved: "badge-success" };

function FacilityLogsPage() {
  const toast = useToast();
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
    if (!form.description.trim()) { toast.warning("Description is required"); return; }
    setCreating(true);
    try {
      const payload = { type: form.type, description: form.description };
      if (form.cost) payload.cost = form.cost;
      await createFacilityLog(payload);
      setModalOpen(false);
      setForm({ type: "water", description: "", cost: "" });
      toast.success("Facility log created");
      fetchLogs();
    } catch (err) {
      const detail = err.response?.data;
      toast.error(typeof detail === "string" ? detail : detail?.detail || "Failed to create log");
    } finally {
      setCreating(false);
    }
  };

  const toggleStatus = async (log) => {
    const newStatus = log.status === "open" ? "resolved" : "open";
    setTogglingId(log.id);
    try {
      await updateFacilityLog(log.id, { status: newStatus });
      toast.success(`Log marked as ${newStatus}`);
      fetchLogs();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update status");
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
        <span className={`badge ${BADGE_MAP[val] || "badge-muted"}`} style={{ textTransform: "capitalize" }}>
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
      render: (_, row) => {
        let label;
        if (togglingId === row.id) {
          label = "…";
        } else if (row.status === "open") {
          label = "Resolve";
        } else {
          label = "Re-open";
        }
        return (
          <Button
            variant={row.status === "open" ? "secondary" : "ghost"}
            size="sm"
            disabled={togglingId === row.id}
            onClick={(e) => { e.stopPropagation(); toggleStatus(row); }}
          >
            {label}
          </Button>
        );
      },
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchLogs} />;

  return (
    <div>
      <div className="page-header">
        <h1>Facility Logs</h1>
        <Button onClick={() => setModalOpen(true)}>+ New Log</Button>
      </div>

      <Table columns={columns} data={logs} emptyMessage="No facility logs" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="New Facility Log">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="label" htmlFor="facility-type">Type *</label>
            <Select
              id="facility-type"
              value={form.type}
              onChange={(v) => setForm((p) => ({ ...p, type: v }))}
              options={[
                { value: "gas", label: "Gas" },
                { value: "water", label: "Water" },
                { value: "electricity", label: "Electricity" },
                { value: "repair", label: "Repair" },
              ]}
            />
          </div>

          <div className="form-group">
            <label className="label" htmlFor="facility-description">Description *</label>
            <textarea
              id="facility-description"
              className="textarea"
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              placeholder="Describe the issue..."
              rows={3}
            />
          </div>

          <Input label="Cost (optional)" type="number" value={form.cost} onChange={(e) => setForm((p) => ({ ...p, cost: e.target.value }))} min="0" step="1000" />

          <div className="form-actions">
            <Button type="submit" disabled={creating}>{creating ? "Saving..." : "Create Log"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default FacilityLogsPage;
