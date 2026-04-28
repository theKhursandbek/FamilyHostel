import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import {
  getSystemSettings,
  updateSystemSettings,
  listIncomeRules,
  createIncomeRule,
  deleteIncomeRule,
  listRolePeople,
  updateRolePersonSalary,
} from "../../services/ceoService";
import { listBranches } from "../../services/branchesService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Select from "../../components/Select";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const SALARY_MODE_OPTIONS = [
  { value: "shift", label: "Shift-based" },
  { value: "per_room", label: "Per-room-based" },
];

const ROLE_CARDS = [
  { id: "director", title: "Director" },
  { id: "administrator", title: "Administrator" },
  { id: "staff", title: "Staff (cleaners)" },
];

function SalarySettingsPage() {
  const toast = useToast();

  const [settings, setSettings] = useState(null);
  const [branches, setBranches] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [activeRole, setActiveRole] = useState(null); // null | "director" | "administrator" | "staff"
  const [savingSettings, setSavingSettings] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, b, r] = await Promise.all([
        getSystemSettings(),
        listBranches(),
        listIncomeRules(),
      ]);
      setSettings(s);
      setBranches(b);
      setRules(r);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load salary settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Quietly refetch only the income rules (no page-level Loader flicker).
  const refreshRules = useCallback(async () => {
    try {
      const r = await listIncomeRules();
      setRules(r);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to refresh rules.");
    }
  }, [toast]);

  // ------------------------------------------------------------------ Settings
  const handleSettingsChange = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  const saveSettings = async (e) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const updated = await updateSystemSettings({
        salary_mode: settings.salary_mode,
        salary_cycle: "monthly",
        staff_shift_rate: settings.staff_shift_rate || "0",
        per_room_rate: settings.per_room_rate || "0",
        director_fixed_salary: settings.director_fixed_salary || "0",
        admin_shift_rate: settings.admin_shift_rate || "0",
        gm_bonus_percent: settings.gm_bonus_percent || "0",
      });
      setSettings(updated);
      toast.success("Salary settings updated. Applies on next cycle.");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save settings.");
    } finally {
      setSavingSettings(false);
    }
  };

  // ------------------------------------------------------------------ Rules
  // Income rules are now managed inside the <IncomeRulesByBranch /> component
  // rendered in the Administrator drill-down. Threshold-based: pick a branch,
  // then add (threshold income, percent) rows under Day or Night.

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchAll} />;
  if (!settings) return <ErrorMessage message="No settings found." onRetry={fetchAll} />;

  // ------------------------------------------------------------------ Renderers
  const formActions = (
    <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
      <Button type="submit" disabled={savingSettings}>
        {savingSettings ? "Saving…" : "Save changes"}
      </Button>
    </div>
  );

  const renderDirector = () => (
    <>
      <form onSubmit={saveSettings} className="card">
        <h3 style={{ marginTop: 0 }}>Director salary</h3>
        <p className="text-muted" style={{ marginTop: -4 }}>
          Fixed monthly salary paid to the director of each branch. Director also receives admin shift income & % income on top
          (configured under Administrator). Changes apply on the <strong>next</strong> salary cycle.
        </p>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
          <Input
            id="director-fixed"
            label="Fixed monthly salary (UZS)"
            type="number"
            min="0"
            step="10000"
            value={settings.director_fixed_salary ?? ""}
            onChange={(e) => handleSettingsChange("director_fixed_salary", e.target.value)}
          />
          <Input
            id="gm-bonus-percent"
            label="General Manager bonus (%)"
            type="number"
            min="0"
            max="500"
            step="0.5"
            value={settings.gm_bonus_percent ?? ""}
            onChange={(e) => handleSettingsChange("gm_bonus_percent", e.target.value)}
            helperText="Applied on top of the fixed salary for directors flagged as General Manager."
          />
        </div>
        {formActions}
      </form>
      <PeopleSalaryList role="director" unitLabel="monthly salary" refreshKey={settings.director_fixed_salary} />
    </>
  );

  const renderAdministrator = () => (
    <>
      <form onSubmit={saveSettings} className="card">
        <h3 style={{ marginTop: 0 }}>Administrator salary</h3>
        <p className="text-muted" style={{ marginTop: -4 }}>
          Per-shift fixed rate. Administrators also earn a percentage of paid-booking income — configure those % brackets
          per branch & shift below. Changes apply on the <strong>next</strong> salary cycle.
        </p>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
          <Input
            id="admin-shift"
            label="Shift rate (UZS)"
            type="number"
            min="0"
            step="1000"
            value={settings.admin_shift_rate ?? ""}
            onChange={(e) => handleSettingsChange("admin_shift_rate", e.target.value)}
          />
        </div>
        {formActions}
      </form>

      <PeopleSalaryList role="administrator" unitLabel="shift rate" refreshKey={settings.admin_shift_rate} />

      <IncomeRulesByBranch
        branches={branches}
        rules={rules}
        onChanged={refreshRules}
      />
    </>
  );

  const renderStaff = () => (
    <>
      <form onSubmit={saveSettings} className="card">
        <h3 style={{ marginTop: 0 }}>Staff (cleaners) salary</h3>
        <p className="text-muted" style={{ marginTop: -4 }}>
          Choose how cleaning staff are paid. <strong>Shift-based</strong> uses the per-shift rate; <strong>Per-room</strong> pays
          per completed cleaning task. Changes apply on the <strong>next</strong> salary cycle.
        </p>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
          <div className="form-group">
            <label className="label" htmlFor="salary-mode">Pay model</label>
            <Select
              id="salary-mode"
              value={settings.salary_mode}
              onChange={(v) => handleSettingsChange("salary_mode", v)}
              options={SALARY_MODE_OPTIONS}
            />
          </div>
          <Input
            id="shift-rate"
            label="Shift rate (UZS)"
            type="number"
            min="0"
            step="1000"
            value={settings.staff_shift_rate ?? ""}
            onChange={(e) => handleSettingsChange("staff_shift_rate", e.target.value)}
          />
          <Input
            id="per-room-rate"
            label="Per-room rate (UZS)"
            type="number"
            min="0"
            step="1000"
            value={settings.per_room_rate}
            onChange={(e) => handleSettingsChange("per_room_rate", e.target.value)}
          />
        </div>
        {formActions}
      </form>
      <PeopleSalaryList
        role="staff"
        unitLabel={settings.salary_mode === "per_room" ? "per-room rate" : "shift rate"}
        refreshKey={`${settings.salary_mode}-${settings.staff_shift_rate}-${settings.per_room_rate}`}
      />
    </>
  );

  // ------------------------------------------------------------------ Drill-down view
  if (activeRole) {
    const role = ROLE_CARDS.find((r) => r.id === activeRole);
    return (
      <div>
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 10,
            marginBottom: 20,
            padding: "12px 16px",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            boxShadow: "var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.04))",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Button variant="secondary" size="sm" onClick={() => setActiveRole(null)}>
            ← Back to roles
          </Button>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, minWidth: 0 }}>
            <span className="text-muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Salary /
            </span>
            <strong style={{ fontSize: 16 }}>{role.title}</strong>
          </div>
        </div>

        {activeRole === "director" && renderDirector()}
        {activeRole === "administrator" && renderAdministrator()}
        {activeRole === "staff" && renderStaff()}
      </div>
    );
  }

  // ------------------------------------------------------------------ Landing view
  const summaryFor = (id) => {
    if (id === "director") {
      return { metric: `${Number(settings.director_fixed_salary || 0).toLocaleString()} UZS`, sub: "fixed / month" };
    }
    if (id === "administrator") {
      return {
        metric: `${Number(settings.admin_shift_rate || 0).toLocaleString()} UZS`,
        sub: `per shift · ${rules.length} % rule${rules.length === 1 ? "" : "s"}`,
      };
    }
    if (id === "staff") {
      const isPerRoom = settings.salary_mode === "per_room";
      return {
        metric: `${Number((isPerRoom ? settings.per_room_rate : settings.staff_shift_rate) || 0).toLocaleString()} UZS`,
        sub: isPerRoom ? "per room" : "per shift",
      };
    }
    return { metric: "", sub: "" };
  };

  return (
    <div>
      <div className="page-header">
        <h1>Salary Settings</h1>
      </div>

      <h3 style={{ margin: "0 0 12px" }}>Configure by role</h3>
      <div className="card-grid">
        {ROLE_CARDS.map((role) => {
          const { metric, sub } = summaryFor(role.id);
          return (
            <div
              key={role.id}
              className="role-card"
              onClick={() => setActiveRole(role.id)}
              onKeyDown={(e) => { if (e.key === "Enter") setActiveRole(role.id); }}
              role="button"
              tabIndex={0}
            >
              <h3 className="role-card__title">{role.title}</h3>
              <div>
                <div className="role-card__metric">{metric}</div>
                <div className="role-card__metric-sub">{sub}</div>
              </div>
              <div className="role-card__cta">Configure →</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default SalarySettingsPage;

// ---------------------------------------------------------------------------
// PeopleSalaryList — per-person salary override table for a role
// ---------------------------------------------------------------------------
function PeopleSalaryList({ role, unitLabel, refreshKey }) {
  const toast = useToast();
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");
  const [savingId, setSavingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listRolePeople(role, { active: 1 });
      setPeople(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load people.");
    } finally {
      setLoading(false);
    }
  }, [role]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const startEdit = (person) => {
    setEditingId(person.id);
    setDraft(person.salary_override ?? person.effective_salary ?? "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraft("");
  };

  const save = async (person, value) => {
    setSavingId(person.id);
    try {
      const updated = await updateRolePersonSalary(role, person.id, value);
      setPeople((prev) => prev.map((p) => (p.id === person.id ? updated : p)));
      toast.success(value === null ? "Reset to default." : "Salary updated.");
      setEditingId(null);
      setDraft("");
    } catch (err) {
      toast.error(err.response?.data?.salary_override || err.response?.data?.detail || "Failed to save.");
    } finally {
      setSavingId(null);
    }
  };

  const fmt = (v) => (v == null ? "—" : `${Number(v).toLocaleString()} UZS`);

  return (
    <div className="card" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0 }}>People in this role</h3>
          <p className="text-muted" style={{ margin: 0 }}>
            Override the default {unitLabel} for individual people. Empty means the role default applies.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={loading}>Refresh</Button>
      </div>

      {loading && <Loader />}
      {error && !loading && <ErrorMessage message={error} onRetry={load} />}
      {!loading && !error && people.length === 0 && (
        <div className="empty-state">No active people in this role.</div>
      )}
      {!loading && !error && people.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Branch</th>
                <th>Effective</th>
                <th style={{ width: 1 }}>Status</th>
                <th style={{ width: 1, textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {people.map((person) => {
                const isEditing = editingId === person.id;
                const isBusy = savingId === person.id;
                return (
                  <tr key={person.id}>
                    <td>{person.full_name}</td>
                    <td>{person.branch_name || "—"}</td>
                    <td>
                      {isEditing ? (
                        <Input
                          id={`sal-${person.id}`}
                          type="number"
                          min="0"
                          step="1000"
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                        />
                      ) : (
                        <strong>{fmt(person.effective_salary)}</strong>
                      )}
                      {!isEditing && person.is_custom && (
                        <span className="text-muted" style={{ marginLeft: 8, fontSize: 12 }}>
                          (default {fmt(person.default_salary)})
                        </span>
                      )}
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          borderRadius: 999,
                          background: person.is_custom ? "var(--accent-soft, #eef2ff)" : "var(--bg-muted, #f3f4f6)",
                          color: person.is_custom ? "var(--accent, #4338ca)" : "var(--text-secondary)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {person.is_custom ? "Custom" : "Default"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      {isEditing ? (
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <Button size="sm" variant="ghost" onClick={cancelEdit} disabled={isBusy}>Cancel</Button>
                          <Button size="sm" onClick={() => save(person, draft === "" ? null : draft)} disabled={isBusy}>
                            {isBusy ? "…" : "Save"}
                          </Button>
                        </div>
                      ) : (
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <Button size="sm" variant="secondary" onClick={() => startEdit(person)}>
                            {person.is_custom ? "Edit" : "Override"}
                          </Button>
                          {person.is_custom && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => save(person, null)}
                              disabled={isBusy}
                            >
                              Reset
                            </Button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

PeopleSalaryList.propTypes = {
  role: PropTypes.oneOf(["director", "administrator", "staff"]).isRequired,
  unitLabel: PropTypes.string.isRequired,
  refreshKey: PropTypes.any,
};

// ---------------------------------------------------------------------------
// IncomeRulesByBranch — branch list → drill-down with Day | Night columns
// ---------------------------------------------------------------------------
function IncomeRulesByBranch({ branches, rules, onChanged }) {
  const toast = useToast();
  const [activeBranchId, setActiveBranchId] = useState(null);
  const [draftDay, setDraftDay] = useState({ min_income: "", percent: "" });
  const [draftNight, setDraftNight] = useState({ min_income: "", percent: "" });
  const [composing, setComposing] = useState({ day: false, night: false });
  const [busy, setBusy] = useState(false);

  const branchRules = (branchId, shift) =>
    rules
      .filter((r) => r.branch === branchId && r.shift_type === shift)
      .sort((a, b) => Number(a.min_income) - Number(b.min_income));

  const branchSummary = (branchId) => {
    const day = branchRules(branchId, "day").length;
    const night = branchRules(branchId, "night").length;
    return { day, night, total: day + night };
  };

  const addRule = async (branchId, shift, draft, resetDraft) => {
    if (!draft.min_income || !draft.percent) {
      toast.warning("Both threshold and percent are required.");
      return;
    }
    setBusy(true);
    try {
      await createIncomeRule({
        branch: branchId,
        shift_type: shift,
        min_income: draft.min_income,
        percent: draft.percent,
      });
      toast.success("Threshold added.");
      resetDraft({ min_income: "", percent: "" });
      // Stay in compose mode so the CEO can keep adding (Trello-style).
      await onChanged();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to add threshold.");
    } finally {
      setBusy(false);
    }
  };

  const removeRule = async (rule) => {
    if (!globalThis.confirm(`Delete this threshold (${Number(rule.min_income).toLocaleString()} UZS @ ${rule.percent}%)?`)) return;
    setBusy(true);
    try {
      await deleteIncomeRule(rule.id);
      toast.success("Threshold deleted.");
      await onChanged();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete.");
    } finally {
      setBusy(false);
    }
  };

  // ---------------- Branch drill-down view ----------------
  if (activeBranchId) {
    const branch = branches.find((b) => b.id === activeBranchId);
    if (!branch) {
      setActiveBranchId(null);
      return null;
    }

    const renderColumn = (shift, draft, setDraft) => {
      const items = branchRules(activeBranchId, shift);
      const inputId = `inc-${shift}`;
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <h4 style={{ margin: 0, textTransform: "capitalize" }}>{shift} shift</h4>

          {items.length === 0 ? (
            <div className="empty-state" style={{ padding: 12, fontSize: 13 }}>
              No thresholds yet.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {items.map((rule) => (
                <div
                  key={rule.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    background: "var(--bg-card, #fff)",
                  }}
                >
                  <div style={{ fontSize: 14 }}>
                    From <strong>{Number(rule.min_income).toLocaleString()} UZS</strong>
                    <span className="text-muted"> → </span>
                    <strong>{rule.percent}%</strong>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => removeRule(rule)} disabled={busy}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}

          {composing[shift] ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                padding: 12,
                border: "1px solid var(--border)",
                borderRadius: 8,
                background: "var(--bg-soft, #f7f8fa)",
              }}
            >
              <div style={{ display: "grid", gridTemplateColumns: "1fr 110px", gap: 8 }}>
                <Input
                  id={`${inputId}-min`}
                  label="Threshold (UZS)"
                  type="number"
                  min="0"
                  step="100000"
                  placeholder="e.g. 40000000"
                  value={draft.min_income}
                  onChange={(e) => setDraft((d) => ({ ...d, min_income: e.target.value }))}
                />
                <Input
                  id={`${inputId}-pct`}
                  label="Percent"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  placeholder="5"
                  value={draft.percent}
                  onChange={(e) => setDraft((d) => ({ ...d, percent: e.target.value }))}
                />
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <Button
                  size="sm"
                  onClick={() =>
                    addRule(activeBranchId, shift, draft, shift === "day" ? setDraftDay : setDraftNight)
                  }
                  disabled={busy}
                >
                  {busy ? "Adding…" : "Add threshold"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setComposing((c) => ({ ...c, [shift]: false }));
                    (shift === "day" ? setDraftDay : setDraftNight)({ min_income: "", percent: "" });
                  }}
                  disabled={busy}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setComposing((c) => ({ ...c, [shift]: true }))}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "10px 12px",
                border: "1px dashed var(--border)",
                borderRadius: 8,
                background: "transparent",
                color: "var(--text-secondary)",
                cursor: "pointer",
                font: "inherit",
                fontSize: 14,
              }}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Add threshold
            </button>
          )}
        </div>
      );
    };

    return (
      <div className="card" style={{ marginTop: 24, padding: 0, overflow: "visible" }}>
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 5,
            background: "var(--bg-card)",
            borderBottom: "1px solid var(--border)",
            borderTopLeftRadius: "var(--radius-lg)",
            borderTopRightRadius: "var(--radius-lg)",
            padding: "14px 20px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Button variant="secondary" size="sm" onClick={() => setActiveBranchId(null)}>
            ← All branches
          </Button>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, minWidth: 0 }}>
            <span className="text-muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Income thresholds /
            </span>
            <strong style={{ fontSize: 16 }}>{branch.name}</strong>
          </div>
        </div>

        <div style={{ padding: "16px 20px 20px" }}>
          <p className="text-muted" style={{ margin: "0 0 16px" }}>
            When a shift income reaches a threshold, the matching percent is paid to the administrator.
            The <strong>highest</strong> threshold ≤ income wins.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 24,
            }}
          >
            {renderColumn("day", draftDay, setDraftDay)}
            {renderColumn("night", draftNight, setDraftNight)}
          </div>
        </div>
      </div>
    );
  }

  // ---------------- Branch list view ----------------
  return (
    <div className="card" style={{ marginTop: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>Income % thresholds</h3>
        <p className="text-muted" style={{ margin: 0 }}>
          Per-branch & shift % cuts on paid-booking income. Pick a branch to manage its day & night thresholds.
        </p>
      </div>

      {branches.length === 0 ? (
        <div className="empty-state">No branches yet.</div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
            gap: 14,
          }}
        >
          {branches.map((branch) => {
            const { day, night, total } = branchSummary(branch.id);
            const initials = branch.name
              .split(/\s+/)
              .slice(0, 2)
              .map((w) => w[0]?.toUpperCase() ?? "")
              .join("");
            return (
              <button
                key={branch.id}
                type="button"
                onClick={() => setActiveBranchId(branch.id)}
                className="threshold-branch-tile"
                style={{
                  position: "relative",
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  padding: 16,
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "var(--bg-card)",
                  cursor: "pointer",
                  textAlign: "left",
                  font: "inherit",
                  color: "inherit",
                  transition: "transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease",
                  overflow: "hidden",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-2px)";
                  e.currentTarget.style.boxShadow = "var(--shadow-md, 0 6px 18px rgba(0,0,0,0.06))";
                  e.currentTarget.style.borderColor = "var(--brand-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "";
                  e.currentTarget.style.boxShadow = "";
                  e.currentTarget.style.borderColor = "var(--border)";
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: "var(--radius-sm, 8px)",
                      background: "var(--brand-primary)",
                      color: "var(--bg-card)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                      fontSize: 14,
                      letterSpacing: 0.5,
                      flexShrink: 0,
                    }}
                  >
                    {initials || "B"}
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 15, lineHeight: 1.2 }}>{branch.name}</div>
                    <div className="text-muted" style={{ fontSize: 12, marginTop: 2 }}>
                      {total} threshold{total === 1 ? "" : "s"}
                    </div>
                  </div>
                  <span
                    className="text-muted"
                    style={{ fontSize: 18, lineHeight: 1, marginLeft: 4 }}
                    aria-hidden
                  >
                    ›
                  </span>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <ShiftChip kind="day" count={day} />
                  <ShiftChip kind="night" count={night} />
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ShiftChip({ kind, count }) {
  const isDay = kind === "day";
  const has = count > 0;

  // Day = soft tinted (light), Night = filled (dark) — both from brand palette.
  let background;
  let color;
  if (!has) {
    background = "var(--bg-soft)";
    color = "var(--text-secondary)";
  } else if (isDay) {
    background = "var(--accent-soft)";
    color = "var(--brand-primary)";
  } else {
    background = "var(--brand-primary)";
    color = "var(--bg-card)";
  }

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 10px",
        borderRadius: "var(--radius-sm, 8px)",
        background,
        color,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      <span aria-hidden style={{ fontSize: 14 }}>{isDay ? "☀" : "☾"}</span>
      <span style={{ textTransform: "capitalize" }}>{kind}</span>
      <span style={{ marginLeft: "auto", opacity: has ? 1 : 0.6 }}>{count}</span>
    </div>
  );
}

ShiftChip.propTypes = {
  kind: PropTypes.oneOf(["day", "night"]).isRequired,
  count: PropTypes.number.isRequired,
};

IncomeRulesByBranch.propTypes = {
  branches: PropTypes.array.isRequired,
  rules: PropTypes.array.isRequired,
  onChanged: PropTypes.func.isRequired,
};
