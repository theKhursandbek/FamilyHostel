import { useState, useEffect, useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import {
  getSalaries,
  previewSalary,
  getSalaryRoster,
  getSalaryAudit,
  exportRosterCsv,
  getSalaryLifecycleStatus,
  payAdvance,
  payFinal,
  payLate,
} from "../../services/salaryService";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import usePersistedBranch from "../../hooks/usePersistedBranch";
import BranchSelector from "../../components/BranchSelector";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";
import Button from "../../components/Button";
import Modal from "../../components/Modal";
import MonthlyAdjustmentsPanel from "./MonthlyAdjustmentsPanel";

// ─────────────────────────── helpers ───────────────────────────

const fmtMoney = (raw) => {
  const n = Number(raw ?? 0);
  if (!Number.isFinite(n)) return "—";
  return `${n.toLocaleString("en-US", { maximumFractionDigits: 0 })} UZS`;
};

/**
 * Render a money amount as a proper ledger figure:
 *   • tabular sans-serif numerals (no italic prose styling)
 *   • muted "UZS" suffix so the number dominates
 *   • zero rendered in a dimmed tone so it reads as "no value" at a glance
 *   • optional negative sign for penalties (caller passes negate=true)
 */
function Money({ value, negate = false, className = "" }) {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) {
    return <span className={`money money--na ${className}`}>—</span>;
  }
  const isZero = n === 0;
  const formatted = Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
  return (
    <span className={`money ${isZero ? "money--zero" : ""} ${className}`}>
      {negate && n !== 0 ? <span className="money__sign">−</span> : null}
      <span className="money__num">{formatted}</span>
      <span className="money__suffix">UZS</span>
    </span>
  );
}
Money.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  negate: PropTypes.bool,
  className: PropTypes.string,
};

const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const fmtDateTime = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
};

const isoLocal = (d) => {
  // Avoid UTC drift from .toISOString().
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

/** Compute monthly period bounds for the given anchor date. */
function computePeriod(anchor) {
  const y = anchor.getFullYear();
  const m = anchor.getMonth();
  const start = new Date(y, m, 1);
  const end = new Date(y, m + 1, 0);
  return { period_start: isoLocal(start), period_end: isoLocal(end) };
}

function shiftPeriod(anchor, delta) {
  const d = new Date(anchor);
  d.setMonth(d.getMonth() + delta);
  return d;
}

const periodLabel = (start) => {
  const s = new Date(start);
  return s.toLocaleDateString(undefined, { month: "long", year: "numeric" });
};

const STATUS_TONE = {
  paid: "is-paid",
  pending: "is-pending",
};

// ─────────────────────────── shared bits ───────────────────────────

function KpiTile({ label, value, sub }) {
  return (
    <div className="salary-kpi">
      <div className="salary-kpi__lbl">{label}</div>
      <div className="salary-kpi__val">{value}</div>
      {sub && <div className="salary-kpi__sub">{sub}</div>}
    </div>
  );
}
KpiTile.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  sub: PropTypes.node,
};

function BreakdownLedger({ data }) {
  if (!data) return null;
  const rows = [
    { label: "Shifts worked", value: `${data.shift_count ?? 0}` },
    { label: "Shift pay", value: fmtMoney(data.shift_pay) },
    { label: "Income bonus", value: fmtMoney(data.income_bonus) },
    { label: "Cleaning bonus", value: fmtMoney(data.cleaning_bonus) },
    { label: "Director fixed", value: fmtMoney(data.director_fixed) },
    { label: "Penalties", value: `− ${fmtMoney(data.penalties)}`, neg: true },
  ];
  return (
    <div className="salary-ledger">
      {rows.map((r) => (
        <div key={r.label} className={`salary-ledger__row${r.neg ? " is-neg" : ""}`}>
          <span className="salary-ledger__lbl">{r.label}</span>
          <span className="salary-ledger__val">{r.value}</span>
        </div>
      ))}
      <div className="salary-ledger__total">
        <span className="salary-ledger__tlbl">Total</span>
        <span className="salary-ledger__tval">{fmtMoney(data.total)}</span>
      </div>
    </div>
  );
}
BreakdownLedger.propTypes = { data: PropTypes.object };

function PeriodNav({ anchor, onAnchor }) {
  const { period_start, period_end } = useMemo(
    () => computePeriod(anchor),
    [anchor],
  );
  return (
    <div className="period-nav">
      <button
        type="button"
        className="period-nav__step"
        onClick={() => onAnchor(shiftPeriod(anchor, -1))}
        aria-label="Previous period"
      >
        ◀
      </button>
      <div className="period-nav__label">
        <span className="period-nav__title">{periodLabel(period_start)}</span>
        <span className="period-nav__range">{period_start} — {period_end}</span>
      </div>
      <button
        type="button"
        className="period-nav__step"
        onClick={() => onAnchor(shiftPeriod(anchor, +1))}
        aria-label="Next period"
      >
        ▶
      </button>
    </div>
  );
}
PeriodNav.propTypes = {
  anchor: PropTypes.instanceOf(Date).isRequired,
  onAnchor: PropTypes.func.isRequired,
};

// ─────────────────────────── personal view (Staff + Administrator) ───────────────────────────

function PersonalSalaryView() {
  const [anchor, setAnchor] = useState(() => new Date());
  const { period_start, period_end } = useMemo(
    () => computePeriod(anchor),
    [anchor],
  );
  const [breakdown, setBreakdown] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, h] = await Promise.all([
        previewSalary({ period_start, period_end }),
        getSalaries({ ordering: "-period_end" }),
      ]);
      setBreakdown(b);
      setHistory(h.results ?? h);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load salary");
    } finally {
      setLoading(false);
    }
  }, [period_start, period_end]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const lastPaid = history.find((r) => r.status === "paid");

  return (
    <div className="salary-shell">
      <div className="page-header">
        <h1>My Salary</h1>
        <PeriodNav anchor={anchor} onAnchor={setAnchor} />
      </div>

      {(() => {
        if (loading) return <Loader />;
        if (error) return <ErrorMessage message={error} onRetry={fetchAll} />;
        return (
        <>
          <section className="salary-hero">
            <div className="salary-hero__head">
              <span className="salary-hero__lbl">Estimated earnings</span>
              <span className="salary-hero__period">{periodLabel(period_start)}</span>
            </div>
            <div className="salary-hero__amount">{fmtMoney(breakdown?.total)}</div>
            <p className="salary-hero__note">
              Live preview — final amount is locked by your director at the end of the period.
            </p>
          </section>

          <section className="salary-panel">
            <h2 className="salary-panel__title">Breakdown</h2>
            <BreakdownLedger data={breakdown} />
          </section>

          <section className="salary-panel">
            <div className="salary-panel__head">
              <h2 className="salary-panel__title">Payment history</h2>
              {lastPaid && (
                <span className="salary-panel__sub">
                  Last paid {fmtDate(lastPaid.updated_at || lastPaid.created_at)} · {fmtMoney(lastPaid.amount)}
                </span>
              )}
            </div>
            {history.length === 0 ? (
              <div className="salary-empty">No salary records yet.</div>
            ) : (
              <table className="salary-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th className="salary-table__num">Amount</th>
                    <th>Status</th>
                    <th>Locked</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((row) => (
                    <tr key={row.id}>
                      <td>{fmtDate(row.period_start)} — {fmtDate(row.period_end)}</td>
                      <td className="salary-table__num">{fmtMoney(row.amount)}</td>
                      <td>
                        <span className={`salary-pill ${STATUS_TONE[row.status] || ""}`}>
                          {row.status}
                        </span>
                      </td>
                      <td className="salary-table__muted">{fmtDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
        );
      })()}
    </div>
  );
}

// ─────────────────────────── late-recovery modal (Q11) ───────────────────────────

function LateRecoveryModal({ open, year, month, onClose, onSubmit }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (open) setReason(""); }, [open]);

  const handle = async () => {
    if (!reason.trim()) return;
    setBusy(true);
    try {
      await onSubmit({ year, month, reason: reason.trim() });
      onClose();
    } finally {
      setBusy(false);
    }
  };

  const monthLabel = open
    ? new Date(year, month - 1, 1).toLocaleDateString(undefined, {
        month: "long", year: "numeric",
      })
    : "";

  return (
    <Modal isOpen={open} onClose={busy ? () => {} : onClose} title="Record late salary payment">
      <div className="override-form">
        <p className="override-form__lead">
          The standard payment window for <b>{monthLabel}</b> has closed.
          Provide a written reason for paying late — this is audited (Q11).
        </p>
        <label className="override-form__field">
          <span>Reason *</span>
          <input
            type="text"
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy}
            placeholder="e.g. bank delay, employee on leave, manual recovery"
          />
        </label>
        <div className="override-form__actions">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={handle} disabled={busy || !reason.trim()}>
            {busy ? "Saving…" : "Pay late"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
LateRecoveryModal.propTypes = {
  open: PropTypes.bool.isRequired,
  year: PropTypes.number,
  month: PropTypes.number,
  onClose: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

// ─────────────────────────── audit drawer ───────────────────────────

const ACTION_LABEL = {
  calculated: "Locked",
  marked_paid: "Paid",
  overridden: "Overridden",
};

function AuditModal({ recordId, onClose }) {
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!recordId) return;
    setLoading(true);
    getSalaryAudit(recordId)
      .then(setLogs)
      .finally(() => setLoading(false));
  }, [recordId]);

  return (
    <Modal isOpen={!!recordId} onClose={onClose} title="Audit trail">
      {(() => {
        if (loading || !logs) return <Loader />;
        if (logs.length === 0) {
          return <div className="salary-empty">No audit entries yet.</div>;
        }
        return (
        <ol className="audit-list">
          {logs.map((log) => (
            <li key={log.id} className={`audit-list__item is-${log.action}`}>
              <div className="audit-list__head">
                <span className="audit-list__action">{ACTION_LABEL[log.action] || log.action}</span>
                <span className="audit-list__when">{fmtDateTime(log.created_at)}</span>
              </div>
              <div className="audit-list__body">
                <span className="audit-list__actor">{log.actor_name}</span>
                {log.before_amount !== null && log.after_amount !== null && log.before_amount !== log.after_amount && (
                  <span className="audit-list__delta">
                    {fmtMoney(log.before_amount)} → <b>{fmtMoney(log.after_amount)}</b>
                  </span>
                )}
                {log.note && <span className="audit-list__note">“{log.note}”</span>}
              </div>
            </li>
          ))}
        </ol>
        );
      })()}
    </Modal>
  );
}
AuditModal.propTypes = {
  recordId: PropTypes.number,
  onClose: PropTypes.func.isRequired,
};

// ─────────────────────────── manager view (CEO only per Q10) ───────────────────────────

function monthLabelOf(year, month) {
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, {
    month: "long", year: "numeric",
  });
}

function ManagerSalaryView({ user, isSuperAdmin }) {
  const toast = useToast();
  const [branchId, setBranchId] = usePersistedBranch(
    "branchScope:salary",
    isSuperAdmin,
    user?.branch_id ?? null,
  );
  const [anchor, setAnchor] = useState(() => new Date());
  const { period_start, period_end } = useMemo(
    () => computePeriod(anchor),
    [anchor],
  );

  const [roster, setRoster] = useState(null);
  const [history, setHistory] = useState([]);
  const [lifecycle, setLifecycle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState(null); // 'advance' | 'final' | 'late'
  const [auditRecordId, setAuditRecordId] = useState(null);
  const [lateOpen, setLateOpen] = useState(false);

  const ceoMustPick = isSuperAdmin && !branchId;

  const fetchAll = useCallback(async () => {
    if (ceoMustPick) {
      setRoster(null);
      setHistory([]);
      setLifecycle(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = { period_start, period_end };
      if (branchId) params.branch = branchId;
      const [r, h, lc] = await Promise.all([
        getSalaryRoster(params),
        getSalaries({
          ...(branchId ? { branch: branchId } : {}),
          ordering: "-period_end",
        }),
        getSalaryLifecycleStatus(),
      ]);
      setRoster(r);
      setHistory(h.results ?? h);
      setLifecycle(lc);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load payroll");
    } finally {
      setLoading(false);
    }
  }, [branchId, period_start, period_end, ceoMustPick]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handlePayAdvance = async () => {
    const cur = lifecycle?.current_month;
    if (!cur) return;
    const ok = globalThis.confirm(
      `Pay advance for ${monthLabelOf(cur.year, cur.month)} for every active employee on every branch? This is audited.`,
    );
    if (!ok) return;
    setBusyAction("advance");
    try {
      const created = await payAdvance({ year: cur.year, month: cur.month });
      const n = Array.isArray(created) ? created.length : 0;
      toast.success(`Advance paid · ${n} record${n === 1 ? "" : "s"} created`);
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to pay advance");
    } finally {
      setBusyAction(null);
    }
  };

  const handlePayFinal = async () => {
    const prev = lifecycle?.previous_month;
    if (!prev) return;
    const ok = globalThis.confirm(
      `Pay remainder for ${monthLabelOf(prev.year, prev.month)} for every active employee on every branch? This is audited.`,
    );
    if (!ok) return;
    setBusyAction("final");
    try {
      const created = await payFinal({ year: prev.year, month: prev.month });
      const n = Array.isArray(created) ? created.length : 0;
      toast.success(`Remainder paid · ${n} record${n === 1 ? "" : "s"} created`);
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to pay remainder");
    } finally {
      setBusyAction(null);
    }
  };

  const handlePayLate = async ({ year, month, reason }) => {
    setBusyAction("late");
    try {
      const created = await payLate({ year, month, reason });
      const n = Array.isArray(created) ? created.length : 0;
      toast.success(`Late payment recorded · ${n} record${n === 1 ? "" : "s"}`);
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to record late payment");
      throw err;
    } finally {
      setBusyAction(null);
    }
  };

  const handleExport = async () => {
    try {
      await exportRosterCsv({
        period_start, period_end,
        ...(branchId ? { branch: branchId } : {}),
      });
      toast.success("CSV downloaded");
    } catch {
      toast.error("CSV export failed");
    }
  };

  const totals = roster?.totals;
  const adv = lifecycle?.advance_window;
  const fin = lifecycle?.final_window;
  const cur = lifecycle?.current_month;
  const prev = lifecycle?.previous_month;
  const advanceLabel = cur
    ? `Pay advance for ${monthLabelOf(cur.year, cur.month)}`
    : "Pay advance";
  let finalLabel = "Pay remainder";
  if (prev) {
    const verb = fin?.has_advance ? "Pay remainder for" : "Pay salary for";
    finalLabel = `${verb} ${monthLabelOf(prev.year, prev.month)}`;
  }

  return (
    <div className="salary-shell">
      <div className="page-header">
        <h1>Salary Records</h1>
        <BranchSelector value={branchId} onChange={setBranchId} />
      </div>

      {ceoMustPick ? (
        <div className="branch-empty">
          <p className="branch-empty__title">Select a branch to begin</p>
          <p className="branch-empty__hint">
            As CEO you oversee every branch&apos;s payroll. Pick one above.
          </p>
        </div>
      ) : (
        <>
          {/* Q11 banner — previous month is overdue. */}
          {lifecycle?.previous_unpaid_banner && prev && (
            <div
              className="error-message"
              style={{
                background: "#fee2e2",
                borderLeft: "4px solid #dc2626",
                padding: "12px 16px",
                marginBottom: 16,
                color: "#7f1d1d",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
              }}
            >
              <div>
                <strong>Salary for {monthLabelOf(prev.year, prev.month)} still unpaid.</strong>
                <div style={{ fontSize: 13, marginTop: 4 }}>
                  The standard window (closed {fin?.end}) has lapsed. Use the
                  manual late-payment recovery to clear it.
                </div>
              </div>
              <Button
                variant="danger"
                onClick={() => setLateOpen(true)}
                disabled={busyAction === "late"}
              >
                Record late payment
              </Button>
            </div>
          )}

          {/* Calendar-driven payroll CTAs (§3.3). */}
          <section className="salary-panel" style={{ marginBottom: 16 }}>
            <div className="salary-panel__head">
              <div>
                <h2 className="salary-panel__title">Payroll lifecycle</h2>
                <span className="salary-panel__sub">
                  Calendar-driven — buttons appear only inside their window.
                  No override (Q11 modal handles late recovery).
                </span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              {(() => {
                if (!adv?.open) return null;
                let label = advanceLabel;
                if (busyAction === "advance") label = "Paying…";
                else if (adv.already_paid) label = `${advanceLabel} (already paid)`;
                return (
                  <Button
                    onClick={handlePayAdvance}
                    disabled={busyAction === "advance" || adv.already_paid}
                    title={adv.already_paid ? "Advance already paid for this month" : ""}
                  >
                    {label}
                  </Button>
                );
              })()}
              {!adv?.open && (
                <span className="salary-panel__sub">
                  Advance window: {adv?.start} → {adv?.end}
                  {adv?.already_paid ? " · already paid" : ""}
                </span>
              )}
              {(() => {
                if (!fin?.open) return null;
                let label = finalLabel;
                if (busyAction === "final") label = "Paying…";
                else if (fin.already_paid) label = `${finalLabel} (already paid)`;
                return (
                  <Button
                    onClick={handlePayFinal}
                    disabled={busyAction === "final" || fin.already_paid}
                    title={fin.already_paid ? "Remainder already paid" : ""}
                  >
                    {label}
                  </Button>
                );
              })()}
              {!fin?.open && (
                <span className="salary-panel__sub">
                  Remainder window: {fin?.start} → {fin?.end}
                  {fin?.already_paid ? " · already paid" : ""}
                </span>
              )}
              {!adv?.open && !fin?.open && (
                <span className="salary-panel__sub">
                  No payroll window open today. Next opens {adv?.start}.
                </span>
              )}
            </div>
          </section>

          <div className="salary-toolbar">
            <PeriodNav anchor={anchor} onAnchor={setAnchor} />
            <div className="salary-toolbar__spacer" />
            <Button variant="secondary" size="sm" onClick={handleExport} disabled={loading}>
              Export CSV
            </Button>
          </div>

          <section className="salary-kpis">
            <KpiTile
              label="Period"
              value={periodLabel(period_start)}
              sub={`${fmtDate(period_start)} — ${fmtDate(period_end)}`}
            />
            <KpiTile label="Headcount" value={loading ? "…" : (totals?.headcount ?? 0)} />
            <KpiTile label="Total payroll" value={loading ? "…" : fmtMoney(totals?.payroll)} />
            <KpiTile
              label="Locked · Paid"
              value={loading ? "…" : `${totals?.locked ?? 0} · ${totals?.paid ?? 0}`}
              sub="this period"
            />
          </section>

          {error && <ErrorMessage message={error} onRetry={fetchAll} />}

          <section className="salary-panel">
            <div className="salary-panel__head">
              <h2 className="salary-panel__title">This period&apos;s payroll preview</h2>
              <span className="salary-panel__sub">
                Live totals — payments are made via the lifecycle buttons above.
              </span>
            </div>

            {(() => {
              if (loading) return <Loader />;
              const rows = roster?.rows ?? [];
              if (rows.length === 0) {
                return <div className="salary-empty">No employees on this branch.</div>;
              }
              return (
                <div className="salary-table-wrap">
                  <table className="salary-table salary-table--roster">
                    <thead>
                      <tr>
                        <th>Employee</th>
                        <th>Role</th>
                        <th className="salary-table__num">Shifts</th>
                        <th className="salary-table__num">Shift pay</th>
                        <th className="salary-table__num">Bonuses</th>
                        <th className="salary-table__num">Penalties</th>
                        <th className="salary-table__num">Total</th>
                        <th>Status</th>
                        <th aria-label="Actions" />
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const bonuses =
                          Number(row.income_bonus || 0) +
                          Number(row.cleaning_bonus || 0) +
                          Number(row.director_fixed || 0);
                        let statusText = "Open";
                        let statusTone = "";
                        if (row.record_status === "paid") {
                          statusText = "Paid"; statusTone = "is-paid";
                        } else if (row.record_id) {
                          statusText = "Locked"; statusTone = "is-pending";
                        }
                        return (
                          <tr key={row.account}>
                            <td className="salary-table__name">{row.account_name}</td>
                            <td className="salary-table__muted">
                              {row.roles?.join(" · ") || "—"}
                            </td>
                            <td className="salary-table__num">{row.shift_count}</td>
                            <td className="salary-table__num">{fmtMoney(row.shift_pay)}</td>
                            <td className="salary-table__num">{fmtMoney(bonuses)}</td>
                            <td className="salary-table__num">− {fmtMoney(row.penalties)}</td>
                            <td className="salary-table__num salary-table__total">
                              {fmtMoney(row.total)}
                            </td>
                            <td>
                              <span className={`salary-pill ${statusTone}`}>{statusText}</span>
                            </td>
                            <td className="salary-table__actions">
                              {row.record_id && (
                                <Button size="sm" variant="ghost" onClick={() => setAuditRecordId(row.record_id)}>
                                  Audit
                                </Button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </section>

          <MonthlyAdjustmentsPanel branchId={branchId} canEdit />

          <section className="salary-panel">
            <div className="salary-panel__head">
              <h2 className="salary-panel__title">History</h2>
              <span className="salary-panel__sub">Persisted records on this branch.</span>
            </div>
            {history.length === 0 ? (
              <div className="salary-empty">No locked records yet.</div>
            ) : (
              <table className="salary-table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Period</th>
                    <th>Kind</th>
                    <th className="salary-table__num">Amount</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((row) => (
                    <tr key={row.id}>
                      <td className="salary-table__name">{row.account_name}</td>
                      <td>{fmtDate(row.period_start)} — {fmtDate(row.period_end)}</td>
                      <td className="salary-table__muted">{row.kind || "final"}</td>
                      <td className="salary-table__num">{fmtMoney(row.amount)}</td>
                      <td>
                        <span className={`salary-pill ${STATUS_TONE[row.status] || ""}`}>
                          {row.status}
                        </span>
                      </td>
                      <td className="salary-table__muted">{fmtDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      <LateRecoveryModal
        open={lateOpen}
        year={prev?.year}
        month={prev?.month}
        onClose={() => setLateOpen(false)}
        onSubmit={handlePayLate}
      />
      <AuditModal
        recordId={auditRecordId}
        onClose={() => setAuditRecordId(null)}
      />
    </div>
  );
}
ManagerSalaryView.propTypes = {
  user: PropTypes.object,
  isSuperAdmin: PropTypes.bool,
};

// ─────────────────────────── entry ───────────────────────────

function SalaryPage() {
  const { user } = useAuth();
  const roles = user?.roles || [];
  // Per April 2026 spec (Q10): only CEO sees the manager UI. Staff,
  // Administrators AND Directors all see the read-only personal view of
  // their own salary. Colleague salaries are visible only via the branch
  // Excel report download.
  const isManager = roles.includes("superadmin");

  if (!isManager) {
    return <PersonalSalaryView />;
  }
  return (
    <ManagerSalaryView user={user} isSuperAdmin />
  );
}

export default SalaryPage;
