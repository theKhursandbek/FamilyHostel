import { useState, useEffect, useCallback } from "react";
import {
  getFacilityLogs,
  approveExpenseRequest,
  rejectExpenseRequest,
  markExpensePaid,
} from "../../services/directorService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Select from "../../components/Select";
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
 * Expense Approvals — REFACTOR_PLAN_2026_04 §7.5 (CEO view).
 *
 * Lists all expense requests across branches. CEO approves (cash | card),
 * rejects with reason, or confirms card transfers as paid.
 */
function ExpenseApprovalsPage() {
  const toast = useToast();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [actingId, setActingId] = useState(null);

  // approve modal state
  const [approving, setApproving] = useState(null);
  const [approveForm, setApproveForm] = useState({
    payment_method: "cash", note: "",
    over_limit_justified: false, over_limit_reason: "",
  });

  // reject modal state
  const [rejecting, setRejecting] = useState(null);
  const [rejectReason, setRejectReason] = useState("");

  const fetchLogs = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params = statusFilter ? { status: statusFilter } : {};
      const data = await getFacilityLogs(params);
      setLogs(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load requests");
    } finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const submitApprove = async (e) => {
    e.preventDefault();
    if (!approving) return;
    setActingId(approving.id);
    try {
      await approveExpenseRequest(approving.id, approveForm);
      toast.success("Approved");
      setApproving(null);
      setApproveForm({
        payment_method: "cash", note: "",
        over_limit_justified: false, over_limit_reason: "",
      });
      fetchLogs();
    } catch (err) {
      const data = err.response?.data;
      const msg = data?.over_limit_justified
        || data?.payment_method
        || data?.detail
        || (typeof data === "string" ? data : "Approval failed");
      toast.error(msg);
    } finally { setActingId(null); }
  };

  const submitReject = async (e) => {
    e.preventDefault();
    if (!rejecting) return;
    if (!rejectReason.trim()) { toast.warning("Reason required"); return; }
    setActingId(rejecting.id);
    try {
      await rejectExpenseRequest(rejecting.id, rejectReason);
      toast.success("Rejected");
      setRejecting(null); setRejectReason("");
      fetchLogs();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Reject failed");
    } finally { setActingId(null); }
  };

  const handleConfirmCard = async (log) => {
    setActingId(log.id);
    try {
      await markExpensePaid(log.id);
      toast.success("Card transfer confirmed");
      fetchLogs();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setActingId(null); }
  };

  const columns = [
    { key: "branch_name", label: "Branch" },
    { key: "type", label: "Type", render: (v) => TYPE_LABELS[v] || v },
    {
      key: "description", label: "Description",
      render: (v) => (
        <span style={{
          maxWidth: 240, display: "inline-block", overflow: "hidden",
          textOverflow: "ellipsis", whiteSpace: "nowrap",
        }} title={v}>{v}</span>
      ),
    },
    {
      key: "cost", label: "Cost",
      render: (v) => `${Number(v || 0).toLocaleString()} сум`,
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
      key: "created_at", label: "Filed",
      render: (v) => (v ? new Date(v).toLocaleDateString() : "—"),
    },
    {
      key: "_actions", label: "",
      render: (_, row) => {
        if (row.status === "pending") {
          return (
            <div style={{ display: "flex", gap: 6 }}>
              <Button size="sm" variant="primary"
                disabled={actingId === row.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setApproving(row);
                }}>Approve</Button>
              <Button size="sm" variant="ghost"
                disabled={actingId === row.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setRejecting(row);
                }}>Reject</Button>
            </div>
          );
        }
        if (row.status === "approved_card") {
          return (
            <Button size="sm" variant="primary"
              disabled={actingId === row.id}
              onClick={(e) => {
                e.stopPropagation();
                handleConfirmCard(row);
              }}>{actingId === row.id ? "…" : "Confirm card paid"}</Button>
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
      <div className="page-header"><h1>Expense Approvals</h1></div>

      <div className="card" style={{
        display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 16,
      }}>
        <div style={{ minWidth: 180 }}>
          <label className="label" htmlFor="ea-status">Status</label>
          <Select id="ea-status" value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: "", label: "All" },
              { value: "pending", label: "Pending" },
              { value: "approved_cash", label: "Approved · cash" },
              { value: "approved_card", label: "Approved · card" },
              { value: "paid", label: "Paid" },
              { value: "rejected", label: "Rejected" },
              { value: "resolved", label: "Resolved" },
            ]} />
        </div>
      </div>

      <Table columns={columns} data={logs}
        emptyMessage="Nothing to review" />

      {/* Approve modal */}
      <Modal isOpen={!!approving} onClose={() => setApproving(null)}
        title={approving
          ? `Approve: ${TYPE_LABELS[approving.type] || approving.type} (${approving.branch_name})`
          : "Approve"}>
        {approving && (
          <form onSubmit={submitApprove}>
            <p style={{ margin: "0 0 12px", color: "var(--muted, #666)" }}>
              {Number(approving.cost).toLocaleString()} сум — {approving.description}
            </p>
            <div className="form-group">
              <label className="label">Payment method *</label>
              <Select value={approveForm.payment_method}
                onChange={(v) => setApproveForm((p) => ({ ...p, payment_method: v }))}
                options={[
                  { value: "cash", label: "Cash (branch drawer)" },
                  { value: "card", label: "Branch card (CEO swipe)" },
                ]} />
            </div>
            <div className="form-group">
              <label className="label" htmlFor="ap-note">Note (optional)</label>
              <textarea id="ap-note" className="textarea" rows={2}
                value={approveForm.note}
                onChange={(e) => setApproveForm((p) => ({ ...p, note: e.target.value }))} />
            </div>
            <div className="form-group">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox"
                  checked={approveForm.over_limit_justified}
                  onChange={(e) => setApproveForm((p) => ({
                    ...p, over_limit_justified: e.target.checked,
                  }))} />
                Override monthly expense limit
              </label>
            </div>
            {approveForm.over_limit_justified && (
              <div className="form-group">
                <label className="label" htmlFor="ap-reason">Override reason *</label>
                <textarea id="ap-reason" className="textarea" rows={2}
                  value={approveForm.over_limit_reason}
                  onChange={(e) => setApproveForm((p) => ({
                    ...p, over_limit_reason: e.target.value,
                  }))} />
              </div>
            )}
            <div className="form-actions">
              <Button type="submit" disabled={actingId === approving.id}>
                {actingId === approving.id ? "Approving…" : "Approve"}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* Reject modal */}
      <Modal isOpen={!!rejecting} onClose={() => setRejecting(null)}
        title={rejecting
          ? `Reject: ${TYPE_LABELS[rejecting.type] || rejecting.type}`
          : "Reject"}>
        {rejecting && (
          <form onSubmit={submitReject}>
            <p style={{ margin: "0 0 12px", color: "var(--muted, #666)" }}>
              {Number(rejecting.cost).toLocaleString()} сум — {rejecting.branch_name}
            </p>
            <div className="form-group">
              <label className="label" htmlFor="rj-reason">Reason *</label>
              <textarea id="rj-reason" className="textarea" rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Explain why this is being rejected." />
            </div>
            <div className="form-actions">
              <Button type="submit" variant="danger"
                disabled={actingId === rejecting.id}>
                {actingId === rejecting.id ? "Rejecting…" : "Reject request"}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}

export default ExpenseApprovalsPage;
