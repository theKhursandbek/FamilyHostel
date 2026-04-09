import { useState, useEffect, useCallback } from "react";
import { getPenalties, createPenalty, deletePenalty, getAccounts } from "../../services/directorService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const TYPE_LABELS = { late: "Late", absence: "Absence" };

function PenaltyManagementPage() {
  const toast = useToast();
  const [penalties, setPenalties] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [form, setForm] = useState({ account: "", type: "late", count: "1", penalty_amount: "", reason: "" });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [penData, accData] = await Promise.all([getPenalties(), getAccounts()]);
      setPenalties(penData.results ?? penData);
      setAccounts(accData.results ?? accData);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.account) { toast.warning("Select a staff member"); return; }
    if (!form.penalty_amount) { toast.warning("Amount is required"); return; }
    setCreating(true);
    try {
      await createPenalty({
        account: Number(form.account),
        type: form.type,
        count: Number(form.count) || 1,
        penalty_amount: form.penalty_amount,
        reason: form.reason,
      });
      setModalOpen(false);
      setForm({ account: "", type: "late", count: "1", penalty_amount: "", reason: "" });
      toast.success("Penalty created");
      fetchData();
    } catch (err) {
      const detail = err.response?.data;
      toast.error(typeof detail === "string" ? detail : detail?.detail || "Failed to create penalty");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id) => {
    if (!globalThis.confirm("Delete this penalty?")) return;
    setDeletingId(id);
    try {
      await deletePenalty(id);
      toast.success("Penalty deleted");
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete");
    } finally {
      setDeletingId(null);
    }
  };

  const columns = [
    {
      key: "account",
      label: "Staff",
      render: (val) => {
        const acc = accounts.find((a) => a.id === val);
        return acc ? (acc.full_name || acc.phone) : `#${val}`;
      },
    },
    { key: "type", label: "Type", render: (val) => TYPE_LABELS[val] || val },
    { key: "count", label: "Count" },
    {
      key: "penalty_amount",
      label: "Amount",
      render: (val) => (val === null || val === undefined ? "—" : `${Number(val).toLocaleString()} сум`),
    },
    { key: "reason", label: "Reason", render: (val) => val || "—" },
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
          variant="danger"
          size="sm"
          disabled={deletingId === row.id}
          onClick={(e) => { e.stopPropagation(); handleDelete(row.id); }}
        >
          {deletingId === row.id ? "…" : "Delete"}
        </Button>
      ),
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchData} />;

  return (
    <div>
      <div className="page-header">
        <h1>Penalty Management</h1>
        <Button onClick={() => setModalOpen(true)}>+ Add Penalty</Button>
      </div>

      <Table columns={columns} data={penalties} emptyMessage="No penalties" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Create Penalty">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="label" htmlFor="penalty-staff">Staff Member *</label>
            <select
              id="penalty-staff"
              className="select"
              value={form.account}
              onChange={(e) => setForm((p) => ({ ...p, account: e.target.value }))}
            >
              <option value="">Select staff</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.phone}{a.full_name ? ` — ${a.full_name}` : ""}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="label" htmlFor="penalty-type">Type *</label>
            <select
              id="penalty-type"
              className="select"
              value={form.type}
              onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}
            >
              <option value="late">Late</option>
              <option value="absence">Absence</option>
            </select>
          </div>

          <Input label="Count" type="number" value={form.count} onChange={(e) => setForm((p) => ({ ...p, count: e.target.value }))} min="1" />
          <Input label="Amount" type="number" value={form.penalty_amount} onChange={(e) => setForm((p) => ({ ...p, penalty_amount: e.target.value }))} required min="0" step="1000" />
          <Input label="Reason (optional)" value={form.reason} onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))} />

          <div className="form-actions">
            <Button type="submit" disabled={creating}>{creating ? "Saving..." : "Create Penalty"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default PenaltyManagementPage;
