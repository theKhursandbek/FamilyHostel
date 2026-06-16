import { useState } from "react";
import PropTypes from "prop-types";
import { createSalaryAdjustment } from "../../../services/reportService";
import { fmtMoney, rawMoney } from "../../../utils/moneyInput";

const fmt = (v) => Number(v || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function Tile({ label, value, sub, tone }) {
  const toneStyle = tone === "neg"
    ? { color: "#b91c1c" }
    : tone === "pos" ? { color: "#15803d" } : {};
  return (
    <div className="salary-kpi" style={{ minWidth: 160 }}>
      <div className="salary-kpi__lbl">{label}</div>
      <div className="salary-kpi__val" style={toneStyle}>{value}</div>
      {sub && <div className="salary-kpi__sub">{sub}</div>}
    </div>
  );
}
Tile.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  sub: PropTypes.node,
  tone: PropTypes.oneOf(["pos", "neg"]),
};

function KpiRow({ data }) {
  if (!data) return null;
  const k = data.kpis || {};
  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      <Tile label="Income" value={`${fmt(k.income_total)} UZS`} tone="pos" />
      <Tile label="Expenses" value={`${fmt(k.expense_total)} UZS`} tone="neg" />
      <Tile label="Net" value={`${fmt(k.net)} UZS`}
            tone={Number(k.net) < 0 ? "neg" : "pos"} />
      <Tile label="Occupancy" value={`${k.occupancy_pct ?? 0}%`}
            sub={`${data.occupancy?.booked_nights ?? 0} of ${(data.occupancy?.rooms ?? 0) * (data.occupancy?.days ?? 0)}`} />
      <Tile label="Cash variance (avg)" value={`${fmt(k.cash_variance_avg)} UZS`}
            sub={`${data.cash_sessions?.count ?? 0} sessions`} />
    </div>
  );
}
KpiRow.propTypes = { data: PropTypes.object };

const INCOME_METHODS = [
  { key: "card_transfer", label: "Card Transfer" },
  { key: "cash",         label: "Cash" },
  { key: "qr",          label: "QR Code" },
  { key: "terminal",    label: "Terminal" },
  { key: "telegram",    label: "Telegram" },
];

const EXPENSE_CATEGORIES = [
  { key: "products",   label: "Products" },
  { key: "detergents", label: "Detergents" },
  { key: "telecom",    label: "Telecom" },
  { key: "repair",     label: "Repair" },
  { key: "utilities",  label: "Utilities" },
  { key: "other",      label: "Other" },
];

const MIN_ADJ = 10_000;

function IncomePanel({ data }) {
  if (!data) return null;
  const rows = data.income?.rows || [];
  const year = data.period?.year;
  const month = data.period?.month;
  const daysInMonth = (year && month) ? new Date(year, month, 0).getDate() : 0;
  const allDates = daysInMonth
    ? Array.from({ length: daysInMonth }, (_, i) => {
        const d = i + 1;
        return `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      })
    : rows.map((r) => r.date);
  const rowMap = Object.fromEntries(rows.map((r) => [r.date, r]));
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Income</h2>
      </div>
      <div className="salary-table-wrap salary-table-wrap--scroll">
        <table className="salary-table">
          <thead>
            <tr>
              <th>Date</th>
              {INCOME_METHODS.map((m) => (
                <th key={m.key} className="salary-table__num">{m.label}</th>
              ))}
              <th className="salary-table__num">Total</th>
            </tr>
          </thead>
          <tbody>
            {allDates.length === 0 && (
              <tr><td colSpan={7} className="salary-empty">No data.</td></tr>
            )}
            {allDates.map((date) => {
              const r = rowMap[date] || {};
              return (
                <tr key={date}>
                  <td className="salary-table__muted">{date}</td>
                  {INCOME_METHODS.map((m) => (
                    <td key={m.key} className="salary-table__num">
                      {Number(r[m.key] || 0) ? fmt(r[m.key]) : <span style={{ opacity: 0.3 }}>—</span>}
                    </td>
                  ))}
                  <td className="salary-table__num salary-table__total">
                    {Number(r.total || 0) ? fmt(r.total) : <span style={{ opacity: 0.3 }}>—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
IncomePanel.propTypes = { data: PropTypes.object };

function ExpensePanel({ data }) {
  if (!data) return null;
  const e = data.expenses || {};
  const cats = e.by_category || {};
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Expenses</h2>
      </div>
      <table className="salary-table">
        <thead>
          <tr>
            <th>Category</th>
            <th className="salary-table__num">Amount (UZS)</th>
          </tr>
        </thead>
        <tbody>
          {EXPENSE_CATEGORIES.map(({ key, label }) => (
            <tr key={key}>
              <td className="salary-table__muted">{label}</td>
              <td className="salary-table__num">
                {Number(cats[key] || 0) ? fmt(cats[key]) : <span style={{ opacity: 0.3 }}>—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
ExpensePanel.propTypes = { data: PropTypes.object };

function PayrollPanel({ data, branchId, year, month, canAddAdjustment, onRefresh }) {
  const rows = data?.salary?.rows || [];

  const [pending, setPending] = useState(null);
  const [form, setForm] = useState({ amount: "", reason: "" });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [amountTouched, setAmountTouched] = useState(false);

  if (!data) return null;

  const openModal = (row, kind, rowTotal) => {
    setPending({ account: row.account, account_name: row.account_name, kind, salary: rowTotal });
    setForm({ amount: "", reason: "" });
    setAmountTouched(false);
    setSaveError("");
  };

  const closeModal = () => {
    if (saving) return;
    setPending(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const amt = Number(rawMoney(form.amount));
    if (!form.amount || amt <= 0) {
      setSaveError("Amount must be greater than zero."); return;
    }
    if (amt < MIN_ADJ) {
      setSaveError(`Minimum amount is ${fmt(MIN_ADJ)} UZS.`); return;
    }
    if (pending.salary > 0 && amt > pending.salary) {
      setSaveError(`Cannot exceed employee’s total salary (${fmt(pending.salary)} UZS).`); return;
    }
    if (!form.reason.trim()) {
      setSaveError("Reason is required."); return;
    }
    setSaving(true); setSaveError("");
    try {
      await createSalaryAdjustment({
        account: pending.account,
        branch: Number(branchId),
        year,
        month,
        kind: pending.kind,
        amount: rawMoney(form.amount),
        reason: form.reason.trim(),
      });
      setPending(null);
      onRefresh?.();
    } catch (err) {
      const d = err.response?.data;
      setSaveError(
        typeof d === "string" ? d : d?.detail || d?.amount || d?.reason || "Failed to save"
      );
    } finally {
      setSaving(false);
    }
  };

  const amountRaw = Number(rawMoney(form.amount));
  const amountError = amountTouched
    ? (!form.amount || amountRaw === 0 ? "Required."
      : amountRaw < MIN_ADJ ? `Minimum is ${fmt(MIN_ADJ)} UZS.`
      : pending?.salary > 0 && amountRaw > pending.salary ? `Cannot exceed ${fmt(pending.salary)} UZS.`
      : null)
    : null;
  const formValid =
    amountRaw >= MIN_ADJ &&
    (!(pending?.salary > 0) || amountRaw <= pending.salary) &&
    form.reason.trim().length > 0;

  return (
    <>
      <section className="salary-panel">
        <div className="salary-panel__head">
          <h2 className="salary-panel__title">Salary</h2>
        </div>
        <div className="salary-table-wrap">
          <table className="salary-table salary-table--roster">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Role</th>
                <th className="salary-table__num">Shifts</th>
                <th className="salary-table__num">Shift pay</th>
                <th className="salary-table__num">Bonuses</th>
                <th className="salary-table__num">Total</th>
                <th className="salary-table__num">Penalties</th>
                <th className="salary-table__num">Final</th>
                {canAddAdjustment && <th aria-label="Adjustments" />}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td colSpan={canAddAdjustment ? 9 : 8} className="salary-empty">No employees.</td></tr>
              )}
              {rows.map((r) => {
                const bonuses =
                  Number(r.income_bonus || 0) +
                  Number(r.cleaning_bonus || 0) +
                  Number(r.director_fixed || 0) +
                  Number(r.adjustment_bonus_plus || 0);
                const penalties =
                  Number(r.penalties || 0) + Number(r.adjustment_penalty || 0);
                const rowTotal = Number(r.shift_pay || 0) + bonuses;
                const rowFinal = rowTotal - penalties;
                return (
                  <tr key={r.account}>
                    <td className="salary-table__name">{r.account_name}</td>
                    <td className="salary-table__muted">{r.roles?.join(" · ") || "—"}</td>
                    <td className="salary-table__num">{r.shift_count}</td>
                    <td className="salary-table__num">{fmt(r.shift_pay)}</td>
                    <td className="salary-table__num">{fmt(bonuses)}</td>
                    <td className="salary-table__num salary-table__total">{fmt(rowTotal)}</td>
                    <td className="salary-table__num">− {fmt(penalties)}</td>
                    <td className="salary-table__num">{fmt(rowFinal)}</td>
                    {canAddAdjustment && (
                      <td className="salary-table__actions" style={{ whiteSpace: "nowrap" }}>
                        <button
                          type="button"
                          className="adj-btn adj-btn--plus"
                          title="Add bonus"
                          onClick={() => openModal(r, "bonus_plus", rowTotal)}
                        >+</button>
                        <button
                          type="button"
                          className="adj-btn adj-btn--minus"
                          title="Add penalty"
                          onClick={() => openModal(r, "penalty", rowTotal)}
                        >−</button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Adjustment modal */}
      {pending && (
        <div
          className="adj-modal-backdrop"
          role="presentation"
          onClick={closeModal}
          onKeyDown={(e) => e.key === "Escape" && closeModal()}
        >
          <div
            className="adj-modal"
            role="dialog"
            aria-modal="true"
            aria-label={pending.kind === "bonus_plus" ? "Add Bonus" : "Add Penalty"}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <div className="adj-modal__head">
              <span className="adj-modal__title">
                {pending.kind === "bonus_plus" ? "Add Bonus" : "Add Penalty"} — {pending.account_name}
              </span>
            </div>
            <form onSubmit={handleSubmit} className="adj-modal__body">
              <div className="form-group">
                <label className="label" htmlFor="adj-amount">Amount (UZS) *</label>
                <input
                  id="adj-amount"
                  className={`input${amountError ? " error" : ""}`}
                  type="text"
                  inputMode="numeric"
                  required
                  value={fmtMoney(form.amount)}
                  onChange={(e) => {
                    const raw = rawMoney(e.target.value);
                    if (pending.salary > 0 && Number(raw) > pending.salary) return;
                    setForm((p) => ({ ...p, amount: fmtMoney(e.target.value) }));
                  }}
                  onBlur={() => setAmountTouched(true)}
                  disabled={saving}
                />
                {amountError
                  ? <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--brand-danger)" }}>{amountError}</p>
                  : <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-muted)" }}>
                      Min: {fmtMoney(String(MIN_ADJ))} UZS
                      {pending.salary > 0 && <> · Max: {fmtMoney(String(pending.salary))} UZS</>}
                    </p>
                }
              </div>
              <div className="form-group">
                <label className="label" htmlFor="adj-reason">Reason *</label>
                <textarea
                  id="adj-reason"
                  className="textarea"
                  rows={2}
                  required
                  value={form.reason}
                  onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
                  disabled={saving}
                />
              </div>
              {saveError && (
                <div className="alert alert-error" style={{ marginBottom: 8 }}>{saveError}</div>
              )}
              <div className="adj-modal__actions">
                <button type="button" className="adj-modal__btn adj-modal__btn--cancel" onClick={closeModal} disabled={saving}>Cancel</button>
                <button
                  type="submit"
                  className={`adj-modal__btn ${pending.kind === "bonus_plus" ? "adj-modal__btn--confirm-bonus" : "adj-modal__btn--confirm-penalty"}`}
                  disabled={saving || !formValid}
                >
                  {(() => {
                    if (saving) return "Saving…";
                    return pending.kind === "bonus_plus" ? "Add Bonus" : "Add Penalty";
                  })()}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
PayrollPanel.propTypes = {
  data: PropTypes.object,
  branchId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  year: PropTypes.number,
  month: PropTypes.number,
  canAddAdjustment: PropTypes.bool,
  onRefresh: PropTypes.func,
};

function CashPanel({ data }) {
  if (!data) return null;
  const c = data.cash_sessions || {};
  const statusRows = Object.entries(c.by_status || {});
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Cash sessions</h2>
      </div>
      <table className="salary-table">
        <thead>
          <tr>
            <th>Status</th>
            <th className="salary-table__num">Count</th>
          </tr>
        </thead>
        <tbody>
          {statusRows.length === 0 && (
            <tr><td colSpan={2} className="salary-empty">No sessions.</td></tr>
          )}
          {statusRows.map(([k, v]) => (
            <tr key={k}>
              <td className="salary-table__muted" style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}</td>
              <td className="salary-table__num">{v}</td>
            </tr>
          ))}
          {c.variance_avg != null && (
            <tr>
              <td className="salary-table__muted">Avg variance</td>
              <td className="salary-table__num">{fmt(c.variance_avg)} UZS</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
CashPanel.propTypes = { data: PropTypes.object };

function BranchDashboard({ data, branchId, year, month, canAddAdjustment, onRefresh }) {
  if (!data) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="salary-panel">
        <div className="salary-panel__head">
          <h2 className="salary-panel__title">{data.branch?.name}</h2>
        </div>
        <KpiRow data={data} />
      </div>
      <IncomePanel data={data} />
      <PayrollPanel
        data={data}
        branchId={branchId}
        year={year}
        month={month}
        canAddAdjustment={canAddAdjustment}
        onRefresh={onRefresh}
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
        <ExpensePanel data={data} />
        <CashPanel data={data} />
      </div>
    </div>
  );
}
BranchDashboard.propTypes = {
  data: PropTypes.object,
  branchId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  year: PropTypes.number,
  month: PropTypes.number,
  canAddAdjustment: PropTypes.bool,
  onRefresh: PropTypes.func,
};

export default BranchDashboard;
