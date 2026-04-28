import PropTypes from "prop-types";

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

function IncomePanel({ data }) {
  if (!data) return null;
  const rows = data.income?.rows || [];
  const methods = data.income_methods || {};
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Income</h2>
        <span className="salary-panel__sub">Daily breakdown · payment-method totals</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16 }}>
        <div className="salary-table-wrap" style={{ maxHeight: 320, overflow: "auto" }}>
          <table className="salary-table">
            <thead>
              <tr>
                <th>Date</th>
                <th className="salary-table__num">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td colSpan={2} className="salary-empty">No bookings.</td></tr>
              )}
              {rows.map((r) => (
                <tr key={r.date}>
                  <td className="salary-table__muted">{r.date}</td>
                  <td className="salary-table__num">{fmt(r.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <table className="salary-table">
            <thead>
              <tr>
                <th>Method</th>
                <th className="salary-table__num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(methods).length === 0 && (
                <tr><td colSpan={2} className="salary-empty">—</td></tr>
              )}
              {Object.entries(methods).map(([k, v]) => (
                <tr key={k}>
                  <td className="salary-table__muted">{k}</td>
                  <td className="salary-table__num">{fmt(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
        <span className="salary-panel__sub">
          Cash {fmt(e.cash_total)} · Card {fmt(e.card_total)} · Total {fmt(e.total)} UZS
        </span>
      </div>
      <table className="salary-table">
        <thead>
          <tr>
            <th>Category</th>
            <th className="salary-table__num">Amount (UZS)</th>
          </tr>
        </thead>
        <tbody>
          {Object.keys(cats).length === 0 && (
            <tr><td colSpan={2} className="salary-empty">No expenses.</td></tr>
          )}
          {Object.entries(cats).map(([k, v]) => (
            <tr key={k}>
              <td className="salary-table__muted">{k}</td>
              <td className="salary-table__num">{fmt(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
ExpensePanel.propTypes = { data: PropTypes.object };

function PenaltyPanel({ data }) {
  if (!data) return null;
  const rows = data.penalties || [];
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Penalties</h2>
        <span className="salary-panel__sub">{rows.length} entries this month</span>
      </div>
      <table className="salary-table">
        <thead>
          <tr>
            <th>Person</th>
            <th>Type</th>
            <th className="salary-table__num">Amount</th>
            <th>Reason</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={5} className="salary-empty">No penalties.</td></tr>
          )}
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="salary-table__name">{r.account_name}</td>
              <td className="salary-table__muted">{r.type || "—"}</td>
              <td className="salary-table__num">− {fmt(r.amount)}</td>
              <td className="salary-table__muted">{r.reason || "—"}</td>
              <td className="salary-table__muted">
                {new Date(r.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
PenaltyPanel.propTypes = { data: PropTypes.object };

function PayrollPanel({ data }) {
  if (!data) return null;
  const rows = data.salary?.rows || [];
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Payroll roster</h2>
        <span className="salary-panel__sub">
          {rows.length} employees · payroll {fmt(data.salary?.totals?.payroll)} UZS
        </span>
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
              <th className="salary-table__num">Penalties</th>
              <th className="salary-table__num">Advance</th>
              <th className="salary-table__num">Final</th>
              <th className="salary-table__num">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={9} className="salary-empty">No employees.</td></tr>
            )}
            {rows.map((r) => {
              const bonuses =
                Number(r.income_bonus || 0) +
                Number(r.cleaning_bonus || 0) +
                Number(r.director_fixed || 0) +
                Number(r.adjustment_bonus_plus || 0);
              const penalties =
                Number(r.penalties || 0) + Number(r.adjustment_penalty || 0);
              return (
                <tr key={r.account}>
                  <td className="salary-table__name">{r.account_name}</td>
                  <td className="salary-table__muted">{r.roles?.join(" · ") || "—"}</td>
                  <td className="salary-table__num">{r.shift_count}</td>
                  <td className="salary-table__num">{fmt(r.shift_pay)}</td>
                  <td className="salary-table__num">{fmt(bonuses)}</td>
                  <td className="salary-table__num">− {fmt(penalties)}</td>
                  <td className="salary-table__num">{fmt(r.advance_paid)}</td>
                  <td className="salary-table__num">{fmt(r.final_paid)}</td>
                  <td className="salary-table__num salary-table__total">{fmt(r.total)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
PayrollPanel.propTypes = { data: PropTypes.object };

function CashPanel({ data }) {
  if (!data) return null;
  const c = data.cash_sessions || {};
  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <h2 className="salary-panel__title">Cash sessions</h2>
        <span className="salary-panel__sub">
          {c.count} sessions · {c.closed} closed · variance sum {fmt(c.variance_sum)}
        </span>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {Object.entries(c.by_status || {}).map(([k, v]) => (
          <Tile key={k} label={k} value={v} />
        ))}
        <Tile label="Avg variance" value={`${fmt(c.variance_avg)} UZS`} />
      </div>
    </section>
  );
}
CashPanel.propTypes = { data: PropTypes.object };

function BranchDashboard({ data }) {
  if (!data) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="salary-panel">
        <div className="salary-panel__head">
          <h2 className="salary-panel__title">{data.branch?.name}</h2>
          <span className="salary-panel__sub">
            {MONTHS[(data.period?.month ?? 1) - 1]} {data.period?.year} ·
            {" "}{data.period?.start} → {data.period?.end} ·
            {" "}working days {data.branch?.working_days_per_month}
          </span>
        </div>
        <KpiRow data={data} />
      </div>
      <IncomePanel data={data} />
      <ExpensePanel data={data} />
      <PayrollPanel data={data} />
      <PenaltyPanel data={data} />
      <CashPanel data={data} />
    </div>
  );
}
BranchDashboard.propTypes = { data: PropTypes.object };

export default BranchDashboard;
