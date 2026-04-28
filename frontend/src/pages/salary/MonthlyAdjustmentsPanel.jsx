import { useState, useEffect, useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import {
  getSalaryAdjustments,
  createSalaryAdjustment,
  deleteSalaryAdjustment,
  getSalaryAdjustmentTargets,
} from "../../services/reportService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Loader from "../../components/Loader";
import Select from "../../components/Select";
import Input from "../../components/Input";
import Modal from "../../components/Modal";

/**
 * Monthly Adjustments — list + modal UX (REFACTOR_PLAN_2026_04 §3.7, Q2 Option B).
 *
 * Two header CTAs ("+ Add Penalty" / "+ Add Bonus +") open a modal that
 * creates one ``SalaryAdjustment`` row. Each row is a free-form penalty
 * or bonus with a written reason. Advance is *not* an adjustment any
 * more — it is auto-computed by the salary lifecycle (§3.4).
 */

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const KIND_LABEL = { penalty: "Penalty", bonus_plus: "Bonus +" };
const MODAL_TITLE = { penalty: "Add Penalty", bonus_plus: "Add Bonus +" };
const SUBMIT_LABEL = { penalty: "Add Penalty", bonus_plus: "Add Bonus +" };

function fmtMoney(v) {
  const n = Number(v || 0);
  return Number.isFinite(n) ? n.toLocaleString() : "—";
}

function MonthlyAdjustmentsPanel({ branchId, canEdit }) {
  const toast = useToast();
  const today = new Date();
  const [year, setYear] = useState(String(today.getFullYear()));
  const [month, setMonth] = useState(String(today.getMonth() + 1));
  const [rows, setRows] = useState([]);
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [modalKind, setModalKind] = useState(null); // 'penalty' | 'bonus_plus' | null
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ account: "", amount: "", reason: "" });

  const load = useCallback(async () => {
    if (!branchId) {
      setRows([]);
      setTargets([]);
      return;
    }
    try {
      setLoading(true);
      const [list, targetList] = await Promise.all([
        getSalaryAdjustments({
          branchId, year: Number(year), month: Number(month),
        }),
        getSalaryAdjustmentTargets({ branchId }),
      ]);
      setRows(Array.isArray(list) ? list : []);
      setTargets(Array.isArray(targetList) ? targetList : []);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to load adjustments");
    } finally {
      setLoading(false);
    }
  }, [branchId, year, month, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const openModal = (kind) => {
    setForm({ account: "", amount: "", reason: "" });
    setModalKind(kind);
  };

  const closeModal = () => {
    if (creating) return;
    setModalKind(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.account) { toast.warning("Select an employee"); return; }
    if (!form.amount || Number(form.amount) <= 0) {
      toast.warning("Amount must be greater than zero"); return;
    }
    if (!form.reason.trim()) { toast.warning("Reason is required"); return; }
    setCreating(true);
    try {
      await createSalaryAdjustment({
        account: Number(form.account),
        branch: Number(branchId),
        year: Number(year),
        month: Number(month),
        kind: modalKind,
        amount: form.amount,
        reason: form.reason.trim(),
      });
      toast.success(
        modalKind === "penalty" ? "Penalty added" : "Bonus + added",
      );
      setModalKind(null);
      load();
    } catch (err) {
      const detail = err.response?.data;
      const msg = typeof detail === "string"
        ? detail
        : detail?.detail || detail?.account || detail?.amount || detail?.reason
          || "Failed to save adjustment";
      toast.error(typeof msg === "string" ? msg : "Failed to save adjustment");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (row) => {
    if (!globalThis.confirm(
      `Delete this ${KIND_LABEL[row.kind] || row.kind} for ${row.account_name}?`,
    )) return;
    setDeletingId(row.id);
    try {
      await deleteSalaryAdjustment(row.id);
      toast.success("Adjustment deleted");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete");
    } finally {
      setDeletingId(null);
    }
  };

  const yearOptions = useMemo(() => {
    const cur = today.getFullYear();
    const set = new Set([cur - 1, cur, cur + 1, Number(year)]);
    return [...set]
      .filter((y) => Number.isFinite(y))
      .sort((a, b) => a - b)
      .map((y) => ({ value: String(y), label: String(y) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year]);

  const targetOptions = useMemo(
    () => targets.map((t) => ({
      value: t.account_id,
      label: `${t.full_name} [${t.role === "administrator" ? "Admin" : "Staff"}]`,
    })),
    [targets],
  );

  const totals = useMemo(() => {
    const t = { penalty: 0, bonus_plus: 0 };
    for (const r of rows) {
      const n = Number(r.amount || 0);
      if (r.kind === "penalty") t.penalty += n;
      else if (r.kind === "bonus_plus") t.bonus_plus += n;
    }
    return t;
  }, [rows]);

  return (
    <section className="salary-panel">
      <div className="salary-panel__head">
        <div>
          <h2 className="salary-panel__title">Monthly Adjustments</h2>
          <span className="salary-panel__sub">
            Penalty / Bonus + entries — flow into the monthly Excel report
            and the salary engine. Advance is auto-computed (§3.4).
          </span>
        </div>
        {canEdit && (
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => openModal("penalty")}>
              + Add Penalty
            </Button>
            <Button onClick={() => openModal("bonus_plus")}>
              + Add Bonus +
            </Button>
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "flex-end",
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 140 }}>
          <label className="label" htmlFor="adj-year">Year</label>
          <Select
            id="adj-year"
            value={year}
            onChange={(v) => setYear(v)}
            options={yearOptions}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <label className="label" htmlFor="adj-month">Month</label>
          <Select
            id="adj-month"
            value={month}
            onChange={(v) => setMonth(v)}
            options={MONTHS.map((name, i) => ({
              value: String(i + 1),
              label: name,
            }))}
          />
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 16 }}>
          <div className="salary-kpi" style={{ minWidth: 140 }}>
            <div className="salary-kpi__lbl">Penalties</div>
            <div className="salary-kpi__val">− {fmtMoney(totals.penalty)}</div>
          </div>
          <div className="salary-kpi" style={{ minWidth: 140 }}>
            <div className="salary-kpi__lbl">Bonuses +</div>
            <div className="salary-kpi__val">+ {fmtMoney(totals.bonus_plus)}</div>
          </div>
        </div>
      </div>

      {(() => {
        if (!branchId) {
          return <div className="salary-empty">Select a branch first.</div>;
        }
        if (loading) return <Loader />;
        if (rows.length === 0) {
          return (
            <div className="salary-empty">
              No adjustments for {MONTHS[Number(month) - 1]} {year}.
            </div>
          );
        }
        return (
          <div className="salary-table-wrap">
            <table className="salary-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Type</th>
                  <th className="salary-table__num">Amount</th>
                  <th>Reason</th>
                  <th>Date</th>
                  {canEdit && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="salary-table__name">{row.account_name}</td>
                    <td>
                      <span className={`salary-pill ${row.kind === "penalty" ? "is-pending" : "is-paid"}`}>
                        {KIND_LABEL[row.kind] || row.kind}
                      </span>
                    </td>
                    <td className="salary-table__num">
                      {row.kind === "penalty" ? "− " : "+ "}{fmtMoney(row.amount)}
                    </td>
                    <td className="salary-table__muted">{row.reason || "—"}</td>
                    <td className="salary-table__muted">
                      {row.created_at
                        ? new Date(row.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    {canEdit && (
                      <td className="salary-table__actions">
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={deletingId === row.id}
                          onClick={() => handleDelete(row)}
                        >
                          {deletingId === row.id ? "…" : "Delete"}
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      <Modal
        isOpen={!!modalKind}
        onClose={closeModal}
        title={MODAL_TITLE[modalKind] || ""}
      >
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="label" htmlFor="adj-account">Employee *</label>
            <Select
              id="adj-account"
              value={form.account}
              onChange={(v) => setForm((p) => ({ ...p, account: v }))}
              placeholder="Select admin or staff"
              options={targetOptions}
              emptyText="No admins or staff available"
            />
          </div>
          <Input
            label="Amount *"
            type="number"
            value={form.amount}
            onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))}
            required
            min="0"
            step="1000"
          />
          <Input
            label="Reason *"
            value={form.reason}
            onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
            required
            helperText="Required — explain why."
          />
          <div className="form-actions" style={{ marginTop: 16 }}>
            <Button
              type="button"
              variant="secondary"
              onClick={closeModal}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={creating}>
              {creating ? "Saving…" : (SUBMIT_LABEL[modalKind] || "Save")}
            </Button>
          </div>
        </form>
      </Modal>
    </section>
  );
}

MonthlyAdjustmentsPanel.propTypes = {
  branchId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  canEdit: PropTypes.bool,
};

export default MonthlyAdjustmentsPanel;
