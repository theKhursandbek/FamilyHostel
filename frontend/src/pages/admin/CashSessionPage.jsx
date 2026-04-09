import { useState, useEffect, useCallback } from "react";
import {
  getCashSessions,
  openCashSession,
  closeCashSession,
  handoverCashSession,
  getAccounts,
} from "../../services/adminService";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

function formatMoney(val) {
  if (val === null || val === undefined) return "—";
  return `${Number(val).toLocaleString()} сум`;
}

function SessionCard({ session, onClose, onHandover, actionLoading }) {
  const isOpen = !session.closed_at;
  const isLoading = actionLoading === session.id;

  return (
    <div className={`session-card${isOpen ? " session-open" : ""}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div>
          <strong>Session #{session.id}</strong>
          <span className={`badge ${isOpen ? "badge-success" : "badge-muted"}`} style={{ marginLeft: 8 }}>
            {isOpen ? "Open" : "Closed"}
          </span>
        </div>
        <span className="badge badge-sm" style={{ backgroundColor: session.shift_type === "day" ? "#f59e0b" : "#6366f1" }}>
          {session.shift_type}
        </span>
      </div>

      <div className="text-secondary" style={{ fontSize: 13, display: "flex", flexWrap: "wrap", gap: "4px 20px", marginBottom: 8 }}>
        <span><strong>Admin:</strong> {session.administrator_name || `#${session.administrator}`}</span>
        <span><strong>Opening:</strong> {formatMoney(session.opening_balance)}</span>
        {session.closing_balance != null && <span><strong>Closing:</strong> {formatMoney(session.closing_balance)}</span>}
        {session.difference != null && (
          <span style={{ color: Number(session.difference) < 0 ? "#ef4444" : "#22c55e" }}>
            <strong>Diff:</strong> {formatMoney(session.difference)}
          </span>
        )}
        <span><strong>Opened:</strong> {new Date(session.opened_at).toLocaleString()}</span>
        {session.closed_at && <span><strong>Closed:</strong> {new Date(session.closed_at).toLocaleString()}</span>}
      </div>

      {session.note && <p className="text-secondary" style={{ fontSize: 13, margin: "0 0 8px" }}>{session.note}</p>}

      {isOpen && (
        <div style={{ display: "flex", gap: 8 }}>
          <Button size="sm" disabled={isLoading} onClick={() => onClose(session)}>
            Close Session
          </Button>
          <Button variant="secondary" size="sm" disabled={isLoading} onClick={() => onHandover(session)}>
            Handover
          </Button>
        </div>
      )}
    </div>
  );
}

function CashSessionPage() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  // Open modal
  const [openModal, setOpenModal] = useState(false);
  const [openForm, setOpenForm] = useState({ shift_type: "day", opening_balance: "", note: "" });
  const [openSubmitting, setOpenSubmitting] = useState(false);

  // Close modal
  const [closeModal, setCloseModal] = useState(false);
  const [closeTarget, setCloseTarget] = useState(null);
  const [closeForm, setCloseForm] = useState({ closing_balance: "", note: "" });

  // Handover modal
  const [handoverModal, setHandoverModal] = useState(false);
  const [handoverTarget, setHandoverTarget] = useState(null);
  const [handoverForm, setHandoverForm] = useState({ handed_over_to: "", closing_balance: "", note: "" });
  const [admins, setAdmins] = useState([]);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCashSessions({ ordering: "-opened_at" });
      setSessions(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Open session
  const handleOpenSubmit = async (e) => {
    e.preventDefault();
    if (!openForm.opening_balance) return alert("Opening balance is required");
    setOpenSubmitting(true);
    try {
      await openCashSession({
        shift_type: openForm.shift_type,
        opening_balance: openForm.opening_balance,
        note: openForm.note,
      });
      setOpenModal(false);
      setOpenForm({ shift_type: "day", opening_balance: "", note: "" });
      fetchSessions();
    } catch (err) {
      const detail = err.response?.data;
      alert(typeof detail === "string" ? detail : detail?.detail || "Failed to open session");
    } finally {
      setOpenSubmitting(false);
    }
  };

  // Close session
  const handleCloseClick = (session) => {
    setCloseTarget(session);
    setCloseForm({ closing_balance: "", note: "" });
    setCloseModal(true);
  };

  const handleCloseSubmit = async (e) => {
    e.preventDefault();
    if (!closeForm.closing_balance) return alert("Closing balance is required");
    setActionLoading(closeTarget.id);
    try {
      await closeCashSession(closeTarget.id, closeForm);
      setCloseModal(false);
      fetchSessions();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to close session");
    } finally {
      setActionLoading(null);
    }
  };

  // Handover session
  const handleHandoverClick = async (session) => {
    setHandoverTarget(session);
    setHandoverForm({ handed_over_to: "", closing_balance: "", note: "" });
    setHandoverModal(true);
    try {
      const data = await getAccounts();
      setAdmins((data.results ?? data).filter((a) => a.roles?.includes("administrator")));
    } catch {
      setAdmins([]);
    }
  };

  const handleHandoverSubmit = async (e) => {
    e.preventDefault();
    if (!handoverForm.handed_over_to) return alert("Select next admin");
    if (!handoverForm.closing_balance) return alert("Closing balance is required");
    setActionLoading(handoverTarget.id);
    try {
      await handoverCashSession(handoverTarget.id, {
        handed_over_to: Number(handoverForm.handed_over_to),
        closing_balance: handoverForm.closing_balance,
        note: handoverForm.note,
      });
      setHandoverModal(false);
      fetchSessions();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to handover session");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchSessions} />;

  return (
    <div>
      <div className="page-header">
        <h1>Cash Sessions</h1>
        <Button onClick={() => setOpenModal(true)}>+ Open Session</Button>
      </div>

      {sessions.length === 0 ? (
        <p className="empty-state">No cash sessions.</p>
      ) : (
        sessions.map((s) => (
          <SessionCard
            key={s.id}
            session={s}
            actionLoading={actionLoading}
            onClose={handleCloseClick}
            onHandover={handleHandoverClick}
          />
        ))
      )}

      {/* Open Session Modal */}
      <Modal isOpen={openModal} onClose={() => setOpenModal(false)} title="Open Cash Session">
        <form onSubmit={handleOpenSubmit}>
          <div className="form-group">
            <label className="label">Shift Type *</label>
            <select
              className="select"
              value={openForm.shift_type}
              onChange={(e) => setOpenForm((p) => ({ ...p, shift_type: e.target.value }))}
            >
              <option value="day">Day</option>
              <option value="night">Night</option>
            </select>
          </div>
          <Input label="Opening Balance" type="number" value={openForm.opening_balance} onChange={(e) => setOpenForm((p) => ({ ...p, opening_balance: e.target.value }))} required min="0" step="1000" />
          <Input label="Note (optional)" value={openForm.note} onChange={(e) => setOpenForm((p) => ({ ...p, note: e.target.value }))} />
          <div className="form-actions">
            <Button type="submit" disabled={openSubmitting}>{openSubmitting ? "Opening..." : "Open Session"}</Button>
          </div>
        </form>
      </Modal>

      {/* Close Session Modal */}
      <Modal isOpen={closeModal} onClose={() => setCloseModal(false)} title="Close Cash Session">
        <form onSubmit={handleCloseSubmit}>
          <Input label="Closing Balance" type="number" value={closeForm.closing_balance} onChange={(e) => setCloseForm((p) => ({ ...p, closing_balance: e.target.value }))} required min="0" step="1000" />
          <Input label="Note (optional)" value={closeForm.note} onChange={(e) => setCloseForm((p) => ({ ...p, note: e.target.value }))} />
          <div className="form-actions">
            <Button type="submit">Close Session</Button>
          </div>
        </form>
      </Modal>

      {/* Handover Modal */}
      <Modal isOpen={handoverModal} onClose={() => setHandoverModal(false)} title="Handover Session">
        <form onSubmit={handleHandoverSubmit}>
          <div className="form-group">
            <label className="label">Next Admin *</label>
            <select
              className="select"
              value={handoverForm.handed_over_to}
              onChange={(e) => setHandoverForm((p) => ({ ...p, handed_over_to: e.target.value }))}
            >
              <option value="">Select admin</option>
              {admins.map((a) => (
                <option key={a.id} value={a.id}>{a.phone}{a.full_name ? ` — ${a.full_name}` : ""}</option>
              ))}
            </select>
          </div>
          <Input label="Closing Balance" type="number" value={handoverForm.closing_balance} onChange={(e) => setHandoverForm((p) => ({ ...p, closing_balance: e.target.value }))} required min="0" step="1000" />
          <Input label="Note (optional)" value={handoverForm.note} onChange={(e) => setHandoverForm((p) => ({ ...p, note: e.target.value }))} />
          <div className="form-actions">
            <Button type="submit">Handover</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default CashSessionPage;
