import { useState, useEffect, useCallback } from "react";
import {
  getFacilityLogs,
  createFacilityLog,
  markExpensePaid,
  markExpenseResolved,
} from "../../services/directorService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Select from "../../components/Select";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const TYPE_LABELS = {
  products: "Products",
  detergents: "Detergents",
  telecom: "Telecom",
  repair: "Repair",
  utilities: "Utilities",
  other: "Other",
};
const TYPE_OPTIONS = Object.entries(TYPE_LABELS).map(([value, label]) => ({
  value, label,
}));
const SHIFT_OPTIONS = [
  { value: "", label: "— (none)" },
  { value: "day", label: "Day" },
  { value: "night", label: "Night" },
];
const STATUS_LABEL = {
  pending: "Pending",
  approved_cash: "Approved · cash",
  approved_card: "Approved · card",
  rejected: "Rejected",
  paid: "Paid",
  resolved: "Resolved",
};
const STATUS_BADGE = {
  pending: "badge-warning",
  approved_cash: "badge-info",
  approved_card: "badge-info",
  rejected: "badge-danger",
  paid: "badge-success",
  resolved: "badge-muted",
};

/**
 * Expense Requests — REFACTOR_PLAN_2026_04 §7.5.
 *
 * Director-facing list. The director files requests (status=pending);
 * the CEO approves/rejects via /super-admin/expense-approvals.
 * Once approved as cash, the director taps "Mark cash taken" → paid.
 */
function FacilityLogsPage() {
  const toast = useToast();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [actingId, setActingId] = useState(null);
  const [form, setForm] = useState({
    type: "products", shift_type: "", description: "", cost: "",
  });

  const fetchLogs = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params = statusFilter ? { status: statusFilter } : {};
      const data = await getFacilityLogs(params);
      setLogs(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load expense requests");
    } finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.description.trim()) {
      toast.warning("Description is required"); return;
    }
    setCreating(true);
    try {
      const payload = { type: form.type, description: form.description };
      if (form.cost) payload.cost = form.cost;
      if (form.shift_type) payload.shift_type = form.shift_type;
      await createFacilityLog(payload);
      setModalOpen(false);
      setForm({ type: "products", shift_type: "", description: "", cost: "" });
      toast.success("Expense request filed — awaiting CEO approval");
      fetchLogs();
    } catch (err) {
      const detail = err.response?.data;
      toast.error(typeof detail === "string"
        ? detail : detail?.detail || "Failed to file request");
    } finally { setCreating(false); }
  };

  const handleMarkPaid = async (log) => {
    setActingId(log.id);
    try {
      await markExpensePaid(log.id);
      toast.success("Marked as paid");
      fetchLogs();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setActingId(null); }
  };

  const handleResolve = async (log) => {
    setActingId(log.id);
    try {
      await markExpenseResolved(log.id);
      toast.success("Marked as resolved");
      fetchLogs();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setActingId(null); }
  };

  const columns = [
    { key: "type", label: "Type", render: (v) => TYPE_LABELS[v] || v },
    {
      key: "description", label: "Description",
      render: (v) => (
        <span style={{
          maxWidth: 280, display: "inline-block", overflow: "hidden",
          textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{v}</span>
      ),
    },
    {
      key: "cost", label: "Cost",
      render: (v) => (v == null || v === "0.00"
        ? "—" : `${Number(v).toLocaleString()} сум`),
    },
    {
      key: "status", label: "Status",
      render: (v) => (
        <span className={`badge ${STATUS_BADGE[v] || "badge-muted"}`}>
          {STATUS_LABEL[v] || v}
        </span>
      ),
    },
    {
      key: "approved_at", label: "Approved",
      render: (v) => (v ? new Date(v).toLocaleDateString() : "—"),
    },
    {
      key: "_actions", label: "",
      render: (_, row) => {
        if (row.status === "approved_cash") {
          return (
            <Button
              variant="primary" size="sm"
              disabled={actingId === row.id}
              onClick={(e) => { e.stopPropagation(); handleMarkPaid(row); }}
            >{actingId === row.id ? "…" : "Mark cash taken"}</Button>
          );
        }
        if (row.status === "paid") {
          return (
            <Button
              variant="ghost" size="sm"
              disabled={actingId === row.id}
              onClick={(e) => { e.stopPropagation(); handleResolve(row); }}
            >{actingId === row.id ? "…" : "Resolve"}</Button>
          );
        }
        if (row.status === "rejected" && row.rejection_reason) {
          return (
            <span style={{ color: "var(--danger, #c33)", fontSize: 12 }}
              title={row.rejection_reason}
            >Reason: {row.rejection_reason.slice(0, 40)}…</span>
          );
        }
        return null;
      },
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchLogs} />;

  return (
    <div>
      <div className="page-header">
        <h1>Expense Requests</h1>
        <Button onClick={() => setModalOpen(true)}>+ New Request</Button>
      </div>

      <div className="card" style={{
        display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 16,
      }}>
        <div style={{ minWidth: 180 }}>
          <label className="label" htmlFor="exp-status">Status</label>
          <Select
            id="exp-status" value={statusFilter} onChange={setStatusFilter}
            options={[
              { value: "", label: "All" },
              { value: "pending", label: "Pending" },
              { value: "approved_cash", label: "Approved · cash" },
              { value: "approved_card", label: "Approved · card" },
              { value: "paid", label: "Paid" },
              { value: "resolved", label: "Resolved" },
              { value: "rejected", label: "Rejected" },
            ]}
          />
        </div>
      </div>

      <Table columns={columns} data={logs}
        emptyMessage="No expense requests yet" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)}
        title="New Expense Request">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="label" htmlFor="ex-type">Type *</label>
            <Select id="ex-type" value={form.type}
              onChange={(v) => setForm((p) => ({ ...p, type: v }))}
              options={TYPE_OPTIONS} />
          </div>

          <div className="form-group">
            <label className="label" htmlFor="ex-shift">Shift (optional)</label>
            <Select id="ex-shift" value={form.shift_type}
              onChange={(v) => setForm((p) => ({ ...p, shift_type: v }))}
              options={SHIFT_OPTIONS} />
          </div>

          <div className="form-group">
            <label className="label" htmlFor="ex-desc">Description *</label>
            <textarea id="ex-desc" className="textarea" rows={3}
              value={form.description}
              onChange={(e) => setForm((p) => ({
                ...p, description: e.target.value,
              }))}
              placeholder="What needs to be bought / fixed?" />
          </div>

          <Input label="Cost (сум)" type="number" min="0" step="1000"
            value={form.cost}
            onChange={(e) => setForm((p) => ({ ...p, cost: e.target.value }))} />

          <div className="form-actions">
            <Button type="submit" disabled={creating}>
              {creating ? "Filing…" : "File request"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default FacilityLogsPage;
