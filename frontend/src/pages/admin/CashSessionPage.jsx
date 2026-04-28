import { useState, useEffect, useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import {
  getCashSessions,
  getCashSessionToday,
  openCashSession,
  closeCashSession,
  handoverCashSession,
  reviewCashSession,
  getAccounts,
} from "../../services/adminService";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import Button from "../../components/Button";
import Select from "../../components/Select";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

// ---------- helpers ----------
function fmtMoney(val) {
  if (val === null || val === undefined || val === "") return "—";
  const n = Number(val);
  if (Number.isNaN(n)) return "—";
  return `${n.toLocaleString()} сум`;
}

function fmtDateTime(val) {
  if (!val) return "—";
  const d = new Date(val);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function adminLabelOf(session) {
  return (
    session.admin_name ||
    session.administrator_name ||
    (session.administrator ? `Admin #${session.administrator}` : "—")
  );
}

const SHIFT_LABEL = { day: "Day", night: "Night" };
const REVIEW_BADGE = {
  pending: { label: "Pending review", cls: "badge-warning" },
  approved: { label: "Approved", cls: "badge-success" },
  disputed: { label: "Disputed", cls: "badge-danger" },
};

// ---------- session card ----------
function SessionCard({
  session,
  onClose,
  onHandover,
  onReview,
  actionLoading,
  highlight,
  canReview,
}) {
  const isOpen = session.is_open ?? !session.closed_at;
  const isLoading = actionLoading === session.id;
  const variance = session.variance == null ? null : Number(session.variance);

  return (
    <div
      className="card"
      style={{
        marginBottom: 12,
        borderLeft: highlight
          ? "4px solid var(--brand-primary, #3b82f6)"
          : "4px solid transparent",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div>
          <strong>Session #{session.id}</strong>
          <span
            className={`badge ${isOpen ? "badge-success" : "badge-muted"}`}
            style={{ marginLeft: 8 }}
          >
            {isOpen ? "Open" : "Closed"}
          </span>
          <span className="badge badge-sm" style={{ marginLeft: 6 }}>
            {SHIFT_LABEL[session.shift_type] || session.shift_type}
          </span>
          {!isOpen && session.variance_status && REVIEW_BADGE[session.variance_status] && (
            <span
              className={`badge badge-sm ${REVIEW_BADGE[session.variance_status].cls}`}
              style={{ marginLeft: 6 }}
            >
              {REVIEW_BADGE[session.variance_status].label}
            </span>
          )}
        </div>
        <div className="text-secondary" style={{ fontSize: 13 }}>
          {adminLabelOf(session)}
        </div>
      </div>

      <div
        className="text-secondary"
        style={{
          fontSize: 13,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: "4px 16px",
          marginBottom: 8,
        }}
      >
        <span>
          <strong>Opening:</strong> {fmtMoney(session.opening_balance)}
        </span>
        <span>
          <strong>+ Cash in:</strong> {fmtMoney(session.cash_in)}
        </span>
        <span>
          <strong>− Expenses:</strong> {fmtMoney(session.cash_out)}
        </span>
        <span>
          <strong>Expected:</strong> {fmtMoney(session.expected_balance)}
        </span>
        {session.closing_balance != null && (
          <span>
            <strong>Counted:</strong> {fmtMoney(session.closing_balance)}
          </span>
        )}
        {variance !== null && (
          <span style={{ color: variance < 0 ? "#ef4444" : "#22c55e" }}>
            <strong>Variance:</strong>{" "}
            {variance >= 0 ? "+" : ""}
            {fmtMoney(variance)}
          </span>
        )}
        <span>
          <strong>Opened:</strong>{" "}
          {fmtDateTime(session.opened_at || session.start_time)}
        </span>
        {(session.closed_at || session.end_time) && (
          <span>
            <strong>Closed:</strong>{" "}
            {fmtDateTime(session.closed_at || session.end_time)}
          </span>
        )}
        {session.handed_over_to_name && (
          <span>
            <strong>Handed to:</strong> {session.handed_over_to_name}
          </span>
        )}
      </div>

      {session.note && (
        <p className="text-secondary" style={{ fontSize: 13, margin: "0 0 8px" }}>
          “{session.note}”
        </p>
      )}

      {!isOpen && session.review_comment && (
        <p
          className="text-secondary"
          style={{ fontSize: 12, margin: "0 0 8px", fontStyle: "italic" }}
        >
          Director ({session.reviewed_by_name || "—"}): “{session.review_comment}”
        </p>
      )}

      {isOpen && (
        <div style={{ display: "flex", gap: 8 }}>
          <Button size="sm" disabled={isLoading} onClick={() => onClose(session)}>
            Close Session
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={isLoading}
            onClick={() => onHandover(session)}
          >
            Handover
          </Button>
        </div>
      )}

      {!isOpen && canReview && session.variance_status === "pending" && (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            size="sm"
            variant="primary"
            disabled={isLoading}
            onClick={() => onReview(session, "approved")}
          >
            Approve
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={isLoading}
            onClick={() => onReview(session, "disputed")}
          >
            Dispute
          </Button>
        </div>
      )}
    </div>
  );
}

SessionCard.propTypes = {
  session: PropTypes.shape({
    id: PropTypes.number.isRequired,
    shift_type: PropTypes.string,
    administrator: PropTypes.number,
    administrator_name: PropTypes.string,
    admin_name: PropTypes.string,
    opening_balance: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    closing_balance: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    expected_balance: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    cash_in: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    cash_out: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    variance: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    is_open: PropTypes.bool,
    opened_at: PropTypes.string,
    closed_at: PropTypes.string,
    start_time: PropTypes.string,
    end_time: PropTypes.string,
    note: PropTypes.string,
    handed_over_to_name: PropTypes.string,
    variance_status: PropTypes.string,
    review_comment: PropTypes.string,
    reviewed_by_name: PropTypes.string,
  }).isRequired,
  onClose: PropTypes.func.isRequired,
  onHandover: PropTypes.func.isRequired,
  onReview: PropTypes.func,
  actionLoading: PropTypes.number,
  highlight: PropTypes.bool,
  canReview: PropTypes.bool,
};

// ---------- page ----------
function CashSessionPage() {
  const toast = useToast();
  const { user } = useAuth();
  const roles = user?.roles || [];
  // Director / SuperAdmin can review variances; admin cannot.
  const isDirector =
    roles.includes("director") ||
    roles.includes("superadmin") ||
    roles.includes("super_admin");

  const [sessions, setSessions] = useState([]);
  const [todayInfo, setTodayInfo] = useState({
    open_session: null,
    suggested_shift_type: null,
    previous_close: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  // Open modal
  const [openModal, setOpenModal] = useState(false);
  const [openForm, setOpenForm] = useState({
    shift_type: "day",
    opening_balance: "",
    note: "",
  });
  const [openSubmitting, setOpenSubmitting] = useState(false);

  // Close modal
  const [closeModal, setCloseModal] = useState(false);
  const [closeTarget, setCloseTarget] = useState(null);
  const [closeForm, setCloseForm] = useState({ closing_balance: "", note: "" });

  // Handover modal
  const [handoverModal, setHandoverModal] = useState(false);
  const [handoverTarget, setHandoverTarget] = useState(null);
  const [handoverForm, setHandoverForm] = useState({
    handed_over_to: "",
    closing_balance: "",
    note: "",
  });
  const [admins, setAdmins] = useState([]);

  // Review modal (director only)
  const [reviewModal, setReviewModal] = useState(false);
  const [reviewTarget, setReviewTarget] = useState(null);
  const [reviewDecision, setReviewDecision] = useState("approved");
  const [reviewComment, setReviewComment] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, today] = await Promise.all([
        getCashSessions({ ordering: "-start_time" }),
        getCashSessionToday().catch(() => ({
          open_session: null,
          suggested_shift_type: null,
          previous_close: null,
        })),
      ]);
      setSessions(list.results ?? list);
      setTodayInfo(
        today || {
          open_session: null,
          suggested_shift_type: null,
          previous_close: null,
        },
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // ---- Open ----
  const openOpenModal = () => {
    setOpenForm({
      shift_type: todayInfo.suggested_shift_type || "day",
      opening_balance: "",
      note: "",
    });
    setOpenModal(true);
  };

  const handleOpenSubmit = async (e) => {
    e.preventDefault();
    if (!openForm.opening_balance) {
      toast.warning("Opening balance is required");
      return;
    }
    setOpenSubmitting(true);
    try {
      await openCashSession({
        shift_type: openForm.shift_type,
        opening_balance: openForm.opening_balance,
        note: openForm.note,
      });
      setOpenModal(false);
      toast.success("Cash session opened");
      fetchAll();
    } catch (err) {
      const detail = err.response?.data;
      toast.error(
        typeof detail === "string"
          ? detail
          : detail?.detail || "Failed to open session",
      );
    } finally {
      setOpenSubmitting(false);
    }
  };

  const noteThreshold = useMemo(() => {
    const open = todayInfo.open_session;
    const raw = open?.variance_note_threshold;
    const n = raw == null ? NaN : Number(raw);
    return Number.isFinite(n) ? n : 5000;
  }, [todayInfo]);

  const liveVariance = (target, counted) => {
    if (!target || counted === "" || counted == null) return null;
    const expected = Number(target.expected_balance ?? 0);
    const c = Number(counted);
    if (!Number.isFinite(expected) || !Number.isFinite(c)) return null;
    return c - expected;
  };

  const closeVariance = liveVariance(closeTarget, closeForm.closing_balance);
  const closeNoteRequired =
    closeVariance !== null && Math.abs(closeVariance) > noteThreshold;
  const handoverVariance = liveVariance(
    handoverTarget,
    handoverForm.closing_balance,
  );
  const handoverNoteRequired =
    handoverVariance !== null && Math.abs(handoverVariance) > noteThreshold;

  // ---- Close ----
  const handleCloseClick = (session) => {
    setCloseTarget(session);
    setCloseForm({ closing_balance: "", note: "" });
    setCloseModal(true);
  };

  const handleCloseSubmit = async (e) => {
    e.preventDefault();
    if (!closeForm.closing_balance) {
      toast.warning("Closing balance is required");
      return;
    }
    if (closeNoteRequired && !closeForm.note.trim()) {
      toast.warning(
        `Variance is over ${noteThreshold.toLocaleString()} — a note is required.`,
      );
      return;
    }
    setActionLoading(closeTarget.id);
    try {
      await closeCashSession(closeTarget.id, closeForm);
      setCloseModal(false);
      toast.success("Cash session closed");
      fetchAll();
    } catch (err) {
      const data = err.response?.data;
      toast.error(
        data?.detail || data?.note?.[0] || "Failed to close session",
      );
    } finally {
      setActionLoading(null);
    }
  };

  // ---- Handover ----
  const handleHandoverClick = async (session) => {
    setHandoverTarget(session);
    setHandoverForm({ handed_over_to: "", closing_balance: "", note: "" });
    setHandoverModal(true);
    try {
      const data = await getAccounts();
      setAdmins(
        (data.results ?? data).filter((a) => a.roles?.includes("administrator")),
      );
    } catch {
      setAdmins([]);
      toast.error("Failed to load admin list");
    }
  };

  const handleHandoverSubmit = async (e) => {
    e.preventDefault();
    if (!handoverForm.handed_over_to) {
      toast.warning("Select next admin");
      return;
    }
    if (!handoverForm.closing_balance) {
      toast.warning("Closing balance is required");
      return;
    }
    if (handoverNoteRequired && !handoverForm.note.trim()) {
      toast.warning(
        `Variance is over ${noteThreshold.toLocaleString()} — a note is required.`,
      );
      return;
    }
    setActionLoading(handoverTarget.id);
    try {
      await handoverCashSession(handoverTarget.id, {
        handed_over_to: Number(handoverForm.handed_over_to),
        closing_balance: handoverForm.closing_balance,
        note: handoverForm.note,
      });
      setHandoverModal(false);
      toast.success("Session handed over");
      fetchAll();
    } catch (err) {
      const data = err.response?.data;
      toast.error(
        data?.detail || data?.note?.[0] || "Failed to handover session",
      );
    } finally {
      setActionLoading(null);
    }
  };

  // ---- Review (director only) ----
  const handleReviewClick = (session, decision) => {
    setReviewTarget(session);
    setReviewDecision(decision);
    setReviewComment("");
    setReviewModal(true);
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if (reviewDecision === "disputed" && !reviewComment.trim()) {
      toast.warning("A comment is required to dispute a session.");
      return;
    }
    setReviewSubmitting(true);
    setActionLoading(reviewTarget.id);
    try {
      await reviewCashSession(reviewTarget.id, {
        decision: reviewDecision,
        comment: reviewComment,
      });
      setReviewModal(false);
      toast.success(
        reviewDecision === "approved" ? "Session approved" : "Session disputed",
      );
      fetchAll();
    } catch (err) {
      const data = err.response?.data;
      toast.error(
        data?.detail ||
          data?.comment?.[0] ||
          data?.decision?.[0] ||
          "Failed to submit review",
      );
    } finally {
      setReviewSubmitting(false);
      setActionLoading(null);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchAll} />;

  const myOpen = todayInfo.open_session;
  const history = sessions.filter((s) => !myOpen || s.id !== myOpen.id);

  return (
    <div>
      <div className="page-header">
        <h1>Cash Sessions</h1>
      </div>

      <p
        className="text-secondary"
        style={{ marginTop: -8, marginBottom: 16, maxWidth: 720 }}
      >
        A cash session tracks the physical till for your shift. Open it once at
        the start with the counted cash, and close it at the end after counting
        again. Cash booking payments and facility-log expenses during your shift
        are added/subtracted automatically — the <em>Expected</em> figure is
        what should be in the drawer right now.
      </p>

      {/* Today */}
      <h3 className="section-title">Today</h3>
      {todayInfo.previous_close && (
        <p
          className="text-secondary"
          style={{ fontSize: 13, marginTop: -4, marginBottom: 8 }}
        >
          Previous shift closed at{" "}
          <strong>{fmtMoney(todayInfo.previous_close.closing_balance)}</strong>{" "}
          ({SHIFT_LABEL[todayInfo.previous_close.shift_type] ||
            todayInfo.previous_close.shift_type}
          {todayInfo.previous_close.admin_name
            ? ` — ${todayInfo.previous_close.admin_name}`
            : ""}
          ,{" "}
          {fmtDateTime(todayInfo.previous_close.closed_at)}). Use this as your
          opening balance unless you re-counted.
        </p>
      )}
      {myOpen ? (
        <SessionCard
          session={myOpen}
          actionLoading={actionLoading}
          onClose={handleCloseClick}
          onHandover={handleHandoverClick}
          onReview={handleReviewClick}
          canReview={isDirector}
          highlight
        />
      ) : (
        <div className="card" style={{ marginBottom: 16 }}>
          <p style={{ margin: "4px 0 12px" }}>
            No open session yet. Count the cash in the drawer and open one when
            your shift starts.
          </p>
          <Button onClick={openOpenModal}>+ Open Today’s Session</Button>
        </div>
      )}

      {/* History */}
      <h3 className="section-title" style={{ marginTop: 24 }}>
        History
      </h3>
      {history.length === 0 ? (
        <p className="empty-state">No previous sessions.</p>
      ) : (
        history.map((s) => (
          <SessionCard
            key={s.id}
            session={s}
            actionLoading={actionLoading}
            onClose={handleCloseClick}
            onHandover={handleHandoverClick}
            onReview={handleReviewClick}
            canReview={isDirector}
          />
        ))
      )}

      {/* Open Session Modal */}
      <Modal
        isOpen={openModal}
        onClose={() => setOpenModal(false)}
        title="Open Cash Session"
      >
        <form onSubmit={handleOpenSubmit}>
          <div className="form-group">
            <label className="label" htmlFor="session-shift-type">
              Shift Type *
            </label>
            <Select
              id="session-shift-type"
              value={openForm.shift_type}
              onChange={(v) => setOpenForm((p) => ({ ...p, shift_type: v }))}
              options={[
                { value: "day", label: "Day" },
                { value: "night", label: "Night" },
              ]}
            />
            {todayInfo.suggested_shift_type && (
              <p
                className="text-secondary"
                style={{ fontSize: 12, marginTop: 4 }}
              >
                Pre-filled from your assigned shift today.
              </p>
            )}
          </div>
          <Input
            label="Opening Balance (counted cash)"
            type="number"
            value={openForm.opening_balance}
            onChange={(e) =>
              setOpenForm((p) => ({ ...p, opening_balance: e.target.value }))
            }
            required
            min="0"
            step="1000"
          />
          <Input
            label="Note (optional)"
            value={openForm.note}
            onChange={(e) => setOpenForm((p) => ({ ...p, note: e.target.value }))}
          />
          <div className="form-actions">
            <Button type="submit" disabled={openSubmitting}>
              {openSubmitting ? "Opening..." : "Open Session"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Close Session Modal */}
      <Modal
        isOpen={closeModal}
        onClose={() => setCloseModal(false)}
        title="Close Cash Session"
      >
        <form onSubmit={handleCloseSubmit}>
          {closeTarget && (
            <p
              className="text-secondary"
              style={{ fontSize: 13, marginTop: 0 }}
            >
              Expected in drawer:{" "}
              <strong>{fmtMoney(closeTarget.expected_balance)}</strong>
            </p>
          )}
          {closeVariance !== null && (
            <p
              style={{
                fontSize: 13,
                margin: "0 0 8px",
                color: closeNoteRequired
                  ? "#ef4444"
                  : closeVariance < 0
                    ? "#ef4444"
                    : closeVariance > 0
                      ? "#22c55e"
                      : "inherit",
              }}
            >
              Variance: {closeVariance >= 0 ? "+" : ""}
              {fmtMoney(closeVariance)}
              {closeNoteRequired &&
                ` — over ${noteThreshold.toLocaleString()} threshold, note required.`}
            </p>
          )}
          <Input
            label="Closing Balance (counted cash)"
            type="number"
            value={closeForm.closing_balance}
            onChange={(e) =>
              setCloseForm((p) => ({ ...p, closing_balance: e.target.value }))
            }
            required
            min="0"
            step="1000"
          />
          <Input
            label={closeNoteRequired ? "Note (required)" : "Note (optional)"}
            value={closeForm.note}
            onChange={(e) => setCloseForm((p) => ({ ...p, note: e.target.value }))}
            required={closeNoteRequired}
          />
          <div className="form-actions">
            <Button type="submit" disabled={!!actionLoading}>
              {actionLoading ? "Closing..." : "Close Session"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Handover Modal */}
      <Modal
        isOpen={handoverModal}
        onClose={() => setHandoverModal(false)}
        title="Handover Session"
      >
        <form onSubmit={handleHandoverSubmit}>
          {handoverTarget && (
            <p
              className="text-secondary"
              style={{ fontSize: 13, marginTop: 0 }}
            >
              Expected in drawer:{" "}
              <strong>{fmtMoney(handoverTarget.expected_balance)}</strong>
            </p>
          )}
          {handoverVariance !== null && (
            <p
              style={{
                fontSize: 13,
                margin: "0 0 8px",
                color: handoverNoteRequired
                  ? "#ef4444"
                  : handoverVariance < 0
                    ? "#ef4444"
                    : handoverVariance > 0
                      ? "#22c55e"
                      : "inherit",
              }}
            >
              Variance: {handoverVariance >= 0 ? "+" : ""}
              {fmtMoney(handoverVariance)}
              {handoverNoteRequired &&
                ` — over ${noteThreshold.toLocaleString()} threshold, note required.`}
            </p>
          )}
          <div className="form-group">
            <label className="label" htmlFor="handover-next-admin">
              Next Admin *
            </label>
            <Select
              id="handover-next-admin"
              value={handoverForm.handed_over_to}
              onChange={(v) =>
                setHandoverForm((p) => ({ ...p, handed_over_to: v }))
              }
              placeholder="Select admin"
              options={admins.map((a) => {
                const suffix = a.full_name ? ` — ${a.full_name}` : "";
                return { value: a.id, label: `${a.phone}${suffix}` };
              })}
              emptyText="No admins available"
            />
          </div>
          <Input
            label="Closing Balance (counted cash)"
            type="number"
            value={handoverForm.closing_balance}
            onChange={(e) =>
              setHandoverForm((p) => ({ ...p, closing_balance: e.target.value }))
            }
            required
            min="0"
            step="1000"
          />
          <Input
            label={handoverNoteRequired ? "Note (required)" : "Note (optional)"}
            value={handoverForm.note}
            onChange={(e) =>
              setHandoverForm((p) => ({ ...p, note: e.target.value }))
            }
            required={handoverNoteRequired}
          />
          <div className="form-actions">
            <Button type="submit" disabled={!!actionLoading}>
              {actionLoading ? "Handing over..." : "Handover"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Review Modal (director only) */}
      <Modal
        isOpen={reviewModal}
        onClose={() => setReviewModal(false)}
        title={
          reviewDecision === "approved"
            ? "Approve Cash Session"
            : "Dispute Cash Session"
        }
      >
        <form onSubmit={handleReviewSubmit}>
          {reviewTarget && (
            <p className="text-secondary" style={{ fontSize: 13, marginTop: 0 }}>
              Session #{reviewTarget.id} — variance{" "}
              <strong>{fmtMoney(reviewTarget.variance)}</strong>{" "}
              ({adminLabelOf(reviewTarget)},{" "}
              {SHIFT_LABEL[reviewTarget.shift_type] || reviewTarget.shift_type})
            </p>
          )}
          <Input
            label={
              reviewDecision === "disputed"
                ? "Comment (required)"
                : "Comment (optional)"
            }
            value={reviewComment}
            onChange={(e) => setReviewComment(e.target.value)}
            required={reviewDecision === "disputed"}
          />
          <div className="form-actions">
            <Button
              type="submit"
              variant={reviewDecision === "disputed" ? "danger" : "primary"}
              disabled={reviewSubmitting}
            >
              {reviewSubmitting
                ? "Submitting..."
                : reviewDecision === "approved"
                  ? "Approve"
                  : "Dispute"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default CashSessionPage;
