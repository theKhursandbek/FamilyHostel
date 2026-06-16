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
import { useBranchScope } from "../../context/BranchScopeContext";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Select from "../../components/Select";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

// Format a number with space as thousands separator (e.g. 1 234 567)
const fmtNum = (v) => (v == null ? "" : Math.round(Number(v)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0"));
// Strip spaces/NBSP from a formatted input string → raw digit string
const toRaw = (s) => String(s ?? "").replace(/[\s\u00a0]/g, "");
// Format a raw digit string for display inside an input
const fmtInput = (s) => { const d = toRaw(s).replace(/\D/g, ""); return d.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0"); };

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

  const [activeRole, setActiveRole] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [editModal, setEditModal] = useState(false);
  const [modalTouched, setModalTouched] = useState(false);
  const [modalDraft, setModalDraft] = useState({});

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

  const FIELD_LIMITS = {
    director_fixed_salary: { min: 2000000, max: 100000000 },
    admin_shift_rate:      { min: 50000,   max: 1000000 },
    staff_shift_rate:      { min: 50000,   max: 1000000 },
    per_room_rate:         { min: 10000,   max: 100000 },
  };

  const isFieldInvalid = (field) => {
    if (!modalTouched) return false;
    const v = Number(toRaw(modalDraft[field]));
    const { min, max } = FIELD_LIMITS[field] ?? { min: 50000, max: 1000000 };
    return !modalDraft[field] || isNaN(v) || v < min || v > max;
  };

  const saveSettings = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    setModalTouched(true);
    const fieldsToValidate =
      activeRole === "director" ? ["director_fixed_salary"] :
      activeRole === "administrator" ? ["admin_shift_rate"] :
      activeRole === "staff" ? (modalDraft.salary_mode === "per_room" ? ["per_room_rate"] : ["staff_shift_rate"]) : [];
    for (const field of fieldsToValidate) {
      const v = Number(toRaw(modalDraft[field]));
      const { min, max } = FIELD_LIMITS[field] ?? { min: 50000, max: 1000000 };
      if (!modalDraft[field] || isNaN(v) || v < min || v > max) {
        toast.error(`Value must be between ${fmtNum(min)} and ${fmtNum(max)} UZS.`);
        return false;
      }
    }
    setSavingSettings(true);
    try {
      const updated = await updateSystemSettings({
        salary_mode: modalDraft.salary_mode,
        salary_cycle: "monthly",
        staff_shift_rate: toRaw(modalDraft.staff_shift_rate) || "0",
        per_room_rate: toRaw(modalDraft.per_room_rate) || "0",
        director_fixed_salary: toRaw(modalDraft.director_fixed_salary) || "0",
        admin_shift_rate: toRaw(modalDraft.admin_shift_rate) || "0",
      });
      setSettings(updated);
      setModalDraft({});
      toast.success("Salary settings updated. Applies on next cycle.");
      return true;
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

  const renderDirector = () => (
    <>
      <PeopleSalaryList role="director" unitLabel="monthly salary" refreshKey={settings.director_fixed_salary} showBranchPicker={false} minSalary={2000000} maxSalary={100000000} defaultRate={settings.director_fixed_salary} />

      <Modal isOpen={editModal} onClose={() => { setEditModal(false); setModalTouched(false); setModalDraft({}); }} title="Edit Director Salary">
        <form onSubmit={(e) => { e.preventDefault(); saveSettings().then((ok) => ok && setEditModal(false)); }} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label htmlFor="director-fixed" style={{ display: "block", fontSize: 13, color: "var(--text-muted)", marginBottom: 6 }}>Fixed monthly salary (UZS)</label>
            <input
              id="director-fixed"
              type="text"
              inputMode="numeric"
              value={fmtInput(modalDraft.director_fixed_salary ?? "")}
              onChange={(e) => {
                const raw = toRaw(e.target.value).replace(/\D/g, "");
                if (raw === "" || Number(raw) <= 100000000)
                  setModalDraft((d) => ({ ...d, director_fixed_salary: raw }));
              }}
              autoFocus
              style={{ width: "100%", padding: "8px 12px", border: `1px solid ${isFieldInvalid("director_fixed_salary") ? "var(--brand-danger)" : "var(--border)"}`, borderRadius: "var(--radius-sm, 6px)", fontSize: 15, fontFamily: "inherit", boxSizing: "border-box" }}
            />
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button type="button" onClick={() => { setEditModal(false); setModalTouched(false); setModalDraft({}); }}
              style={{ padding: "10px 18px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", fontSize: 14, fontWeight: 600, fontFamily: "inherit", lineHeight: 1.4, transition: "background 150ms, border-color 150ms" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
            >Cancel</button>
            <Button type="submit" disabled={savingSettings}>{savingSettings ? "…" : "Save"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );

  const renderAdministrator = () => (
    <>
      <IncomeRulesByBranch
        branches={branches}
        rules={rules}
        onChanged={refreshRules}
        activeBranchId={null}
      />

      <PeopleSalaryList role="administrator" unitLabel="shift rate" refreshKey={settings.admin_shift_rate} showBranchPicker={false} defaultRate={settings.admin_shift_rate} />

      <Modal isOpen={editModal} onClose={() => { setEditModal(false); setModalTouched(false); setModalDraft({}); }} title="Edit Administrator Salary">
        <form onSubmit={(e) => { e.preventDefault(); saveSettings().then((ok) => ok && setEditModal(false)); }} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label htmlFor="admin-shift" style={{ display: "block", fontSize: 13, color: "var(--text-muted)", marginBottom: 6 }}>Shift rate (UZS)</label>
            <input
              id="admin-shift"
              type="text"
              inputMode="numeric"
              value={fmtInput(modalDraft.admin_shift_rate ?? "")}
              onChange={(e) => {
                const raw = toRaw(e.target.value).replace(/\D/g, "");
                if (raw === "" || Number(raw) <= 1000000)
                  setModalDraft((d) => ({ ...d, admin_shift_rate: raw }));
              }}
              autoFocus
              style={{ width: "100%", padding: "8px 12px", border: `1px solid ${isFieldInvalid("admin_shift_rate") ? "var(--brand-danger)" : "var(--border)"}`, borderRadius: "var(--radius-sm, 6px)", fontSize: 15, fontFamily: "inherit", boxSizing: "border-box" }}
            />
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button type="button" onClick={() => { setEditModal(false); setModalTouched(false); setModalDraft({}); }}
              style={{ padding: "10px 18px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", fontSize: 14, fontWeight: 600, fontFamily: "inherit", lineHeight: 1.4, transition: "background 150ms, border-color 150ms" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
            >Cancel</button>
            <Button type="submit" disabled={savingSettings}>{savingSettings ? "…" : "Save"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );

  const renderStaff = () => (
    <>
      <PeopleSalaryList
        role="staff"
        unitLabel={settings.salary_mode === "per_room" ? "per-room rate" : "shift rate"}
        refreshKey={`${settings.salary_mode}-${settings.staff_shift_rate}-${settings.per_room_rate}`}
        showBranchPicker={false}
        minSalary={settings.salary_mode === "per_room" ? 10000 : 50000}
        maxSalary={settings.salary_mode === "per_room" ? 100000 : 1000000}
        defaultRate={settings.salary_mode === "per_room" ? settings.per_room_rate : settings.staff_shift_rate}
      />

      <Modal isOpen={editModal} onClose={() => { setEditModal(false); setModalTouched(false); setModalDraft({}); }} title="Edit Staff Salary">
        <form onSubmit={(e) => { e.preventDefault(); saveSettings().then((ok) => ok && setEditModal(false)); }} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label htmlFor="salary-mode" style={{ display: "block", fontSize: 13, color: "var(--text-muted)", marginBottom: 6 }}>Pay model</label>
            <Select
              id="salary-mode"
              value={modalDraft.salary_mode}
              onChange={(v) => setModalDraft((d) => ({ ...d, salary_mode: v }))}
              options={SALARY_MODE_OPTIONS}
            />
          </div>
          {modalDraft.salary_mode !== "per_room" && (
          <div>
            <label htmlFor="staff-shift" style={{ display: "block", fontSize: 13, color: "var(--text-muted)", marginBottom: 6 }}>Shift rate (UZS)</label>
            <input
              id="staff-shift"
              type="text"
              inputMode="numeric"
              value={fmtInput(modalDraft.staff_shift_rate ?? "")}
              onChange={(e) => {
                const raw = toRaw(e.target.value).replace(/\D/g, "");
                if (raw === "" || Number(raw) <= 1000000)
                  setModalDraft((d) => ({ ...d, staff_shift_rate: raw }));
              }}
              style={{ width: "100%", padding: "8px 12px", border: `1px solid ${isFieldInvalid("staff_shift_rate") ? "var(--brand-danger)" : "var(--border)"}`, borderRadius: "var(--radius-sm, 6px)", fontSize: 15, fontFamily: "inherit", boxSizing: "border-box" }}
            />
          </div>
          )}
          {modalDraft.salary_mode === "per_room" && (
          <div>
            <label htmlFor="per-room-rate" style={{ display: "block", fontSize: 13, color: "var(--text-muted)", marginBottom: 6 }}>Per-room rate (UZS)</label>
            <input
              id="per-room-rate"
              type="text"
              inputMode="numeric"
              value={fmtInput(modalDraft.per_room_rate ?? "")}
              onChange={(e) => {
                const raw = toRaw(e.target.value).replace(/\D/g, "");
                if (raw === "" || Number(raw) <= 100000)
                  setModalDraft((d) => ({ ...d, per_room_rate: raw }));
              }}
              style={{ width: "100%", padding: "8px 12px", border: `1px solid ${isFieldInvalid("per_room_rate") ? "var(--brand-danger)" : "var(--border)"}`, borderRadius: "var(--radius-sm, 6px)", fontSize: 15, fontFamily: "inherit", boxSizing: "border-box" }}
            />
          </div>
          )}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button type="button" onClick={() => { setEditModal(false); setModalTouched(false); setModalDraft({}); }}
              style={{ padding: "10px 18px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", fontSize: 14, fontWeight: 600, fontFamily: "inherit", lineHeight: 1.4, transition: "background 150ms, border-color 150ms" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
            >Cancel</button>
            <Button type="submit" disabled={savingSettings}>{savingSettings ? "…" : "Save"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );

  // ------------------------------------------------------------------ Drill-down view
  if (activeRole) {
    const role = ROLE_CARDS.find((r) => r.id === activeRole);
    return (
      <div>
        <div
          style={{
            marginBottom: 20,
            padding: "12px 16px",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            boxShadow: "var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.04))",
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <Button variant="secondary" size="sm" onClick={() => { setActiveRole(null); setEditModal(false); }}>
            ← Back to roles
          </Button>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, minWidth: 0, flex: 1 }}>
            <span className="text-muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Salary /
            </span>
            <strong style={{ fontSize: 16 }}>{role.title}</strong>
          </div>
          <Button size="sm" onClick={() => {
            const clamped = { ...settings };
            for (const [field, { min, max }] of Object.entries(FIELD_LIMITS)) {
              if (clamped[field] !== undefined && clamped[field] !== null) {
                const v = Number(clamped[field]);
                if (!isNaN(v)) clamped[field] = String(Math.min(max, Math.max(min, v)));
              }
            }
            setModalDraft(clamped);
            setEditModal(true);
          }}>Edit rate</Button>
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
      return { metric: `${fmtNum(settings.director_fixed_salary || 0)} UZS`, sub: "fixed / month" };
    }
    if (id === "administrator") {
      return {
        metric: `${fmtNum(settings.admin_shift_rate || 0)} UZS`,
        sub: `per shift · ${rules.length} income rule${rules.length === 1 ? "" : "s"}`,
      };
    }
    if (id === "staff") {
      const isPerRoom = settings.salary_mode === "per_room";
      return {
        metric: `${fmtNum((isPerRoom ? settings.per_room_rate : settings.staff_shift_rate) || 0)} UZS`,
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
function PeopleSalaryList({ role, unitLabel, refreshKey, branchId, onBranchChange, showBranchPicker = true, minSalary = 50000, maxSalary = 1000000, defaultRate = null }) {
  const toast = useToast();
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");
  const [savingId, setSavingId] = useState(null);

  // If no external branchId provided (director/staff tabs), use local state.
  const [localBranchId, setLocalBranchId] = useState(null);
  const effectiveBranchId = onBranchChange ? branchId : localBranchId;
  const setBranchId = onBranchChange ?? setLocalBranchId;

  // Push branch scope into the global fixed header when this panel is visible
  const { register, unregister } = useBranchScope();
  useEffect(() => {
    if (!showBranchPicker) return undefined;
    register(effectiveBranchId, setBranchId);
    return () => unregister();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveBranchId, showBranchPicker, register, unregister]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { active: 1 };
      if (showBranchPicker && effectiveBranchId) params.branch = effectiveBranchId;
      const data = await listRolePeople(role, params);
      setPeople(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load people.");
    } finally {
      setLoading(false);
    }
  }, [role, effectiveBranchId, showBranchPicker]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const startEdit = (person) => {
    setEditingId(person.id);
    const ov = person.salary_override != null ? Number(person.salary_override) : null;
    const raw = (ov !== null && ov >= minSalary && ov <= maxSalary)
      ? person.salary_override
      : (defaultRate ?? person.effective_salary ?? "");
    // Strip to integer string to avoid decimal artifacts (e.g. "10000.00" → "10000")
    const intStr = String(Math.round(Number(String(raw).replace(/[\s\u00a0]/g, ""))));
    setDraft(fmtInput(isNaN(Number(intStr)) ? "" : intStr));
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraft("");
  };

  const save = async (person, value) => {
    if (value !== null) {
      const v = Number(value);
      if (isNaN(v) || v < minSalary || v > maxSalary) {
        toast.error(`Salary must be between ${fmtNum(minSalary)} and ${fmtNum(maxSalary)} UZS.`);
        return;
      }
    }
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

  const fmt = (v) => (v == null ? "—" : `${fmtNum(Math.round(Number(v)))} UZS`);

  return (
    <div className="card" style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: 0 }}>People in this role</h3>
        </div>
      </div>

      {loading && <Loader />}
      {error && !loading && <ErrorMessage message={error} onRetry={load} />}
      {!loading && !error && people.length === 0 && (
        <div className="empty-state">No active people in this role.</div>
      )}
      {!loading && !error && people.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table className="table table-no-hover">
            <thead>
              <tr>
                <th>Name</th>
                {!showBranchPicker && <th>Branch</th>}
                <th style={{ width: 200 }}>Effective {unitLabel && <span style={{ fontWeight: 400, color: "var(--text-muted)", fontSize: 12 }}>({unitLabel})</span>}</th>
                <th style={{ width: 240, textAlign: "right" }}></th>
              </tr>
            </thead>
            <tbody>
              {people.map((person) => {
                const isEditing = editingId === person.id;
                const isBusy = savingId === person.id;
                return (
                  <tr key={person.id} style={{ height: 52, maxHeight: 52, overflow: "hidden" }}>
                    <td style={{ verticalAlign: "middle" }}>{person.full_name}</td>
                    {!showBranchPicker && <td style={{ verticalAlign: "middle" }}>{person.branch_name || "—"}</td>}
                    <td style={{ width: 200, whiteSpace: "nowrap", verticalAlign: "middle" }}>
                      {isEditing ? (
                        <input
                          id={`sal-${person.id}`}
                          type="text"
                          inputMode="numeric"
                          required
                          value={draft}
                          className="input"
                          style={{ width: 150, margin: 0, height: 34, padding: "0 10px", boxSizing: "border-box" }}
                          onChange={(e) => {
                            const raw = toRaw(e.target.value).replace(/\D/g, "");
                            if (raw === "" || Number(raw) <= maxSalary)
                              setDraft(fmtInput(raw));
                          }}
                        />
                      ) : (
                        <strong>{(() => { const ov = person.salary_override != null ? Number(person.salary_override) : null; const v = (ov !== null && ov >= minSalary && ov <= maxSalary) ? person.salary_override : (defaultRate ?? person.effective_salary); return fmt(v); })()}</strong>
                      )}
                    </td>

                    <td style={{ width: 240, textAlign: "right", whiteSpace: "nowrap", verticalAlign: "middle" }}>
                      {isEditing ? (
                        <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                          <button
                            type="button"
                            onClick={cancelEdit}
                            disabled={isBusy}
                            title="Cancel"
                            style={{ padding: "6px 10px", height: 32, border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", display: "flex", alignItems: "center", transition: "background 150ms, border-color 150ms", boxSizing: "border-box" }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                          >
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={() => save(person, draft === "" ? null : toRaw(draft))}
                            disabled={isBusy}
                            title="Save"
                            style={{ padding: "6px 10px", height: 32, border: "1px solid var(--brand-primary)", borderRadius: "var(--radius-sm, 6px)", background: "var(--brand-primary)", cursor: "pointer", color: "#fff", display: "flex", alignItems: "center", transition: "opacity 150ms", boxSizing: "border-box" }}
                            onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.85"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.opacity = "1"; }}
                          >
                            {isBusy ? (
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>
                              </svg>
                            ) : (
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12"/>
                              </svg>
                            )}
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                          {person.salary_override != null && (
                            <button
                              type="button"
                              onClick={() => save(person, null)}
                              disabled={savingId === person.id}
                              title="Reset to default"
                              style={{ padding: "6px 10px", height: 32, border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", display: "flex", alignItems: "center", transition: "background 150ms, border-color 150ms", boxSizing: "border-box" }}
                              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
                              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                                <path d="M3 3v5h5"/>
                              </svg>
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => startEdit(person)}
                            title="Edit"
                            style={{ padding: "6px 12px", height: 32, border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", display: "flex", alignItems: "center", transition: "background 150ms, border-color 150ms", boxSizing: "border-box" }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                          </button>
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
  branchId: PropTypes.number,
  onBranchChange: PropTypes.func,
  showBranchPicker: PropTypes.bool,
};

// ---------------------------------------------------------------------------
// IncomeRulesByBranch — branch list → drill-down with monthly thresholds
// ---------------------------------------------------------------------------
function IncomeRulesByBranch({ branches, rules, onChanged, activeBranchId: initialBranchId }) {
  const toast = useToast();
  const [activeBranchId, setActiveBranchId] = useState(initialBranchId ?? null);
  const [draft, setDraft] = useState({ min_income: "", percent: "" });
  const [composing, setComposing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [touched, setTouched] = useState(false);

  // Keep in sync when the parent branch selector changes.
  useEffect(() => {
    setActiveBranchId(initialBranchId ?? null);
    setComposing(false);
    setTouched(false);
    setDraft({ min_income: "", percent: "" });
  }, [initialBranchId]);

  const branchRules = (branchId) =>
    rules
      .filter((r) => r.branch === branchId)
      .sort((a, b) => Number(a.min_income) - Number(b.min_income));

  const addRule = async (branchId) => {
    setTouched(true);
    // Strip trailing dot first, then validate
    const cleanPercent = draft.percent.replace(/\.$/, "");
    if (!toRaw(draft.min_income) || !cleanPercent) return;

    const existing = branchRules(branchId);
    const rawIncome = toRaw(draft.min_income);

    if (Number(rawIncome) < 1000000) {
      toast.error("Minimum income threshold is 1 000 000 UZS.");
      return;
    }
    if (existing.some((r) => Number(r.min_income) === Number(rawIncome))) {
      toast.error("A threshold with this income amount already exists.");
      return;
    }
    // Monotonic percent: lower income → lower (or equal) percent, higher income → higher (or equal) percent
    const newIncome = Number(rawIncome);
    const newPct = Number(cleanPercent);
    const below = existing.filter((r) => Number(r.min_income) < newIncome);
    const above = existing.filter((r) => Number(r.min_income) > newIncome);
    if (below.length > 0) {
      const maxBelowPct = Math.max(...below.map((r) => Number(r.percent)));
      if (newPct < maxBelowPct) {
        toast.error(`Percentage must be at least ${maxBelowPct}% (the rate for the previous lower threshold).`);
        return;
      }
    }
    if (above.length > 0) {
      const minAbovePct = Math.min(...above.map((r) => Number(r.percent)));
      if (newPct > minAbovePct) {
        toast.error(`Percentage must be at most ${minAbovePct}% (the rate for the next higher threshold).`);
        return;
      }
    }

    setBusy(true);
    try {
      await createIncomeRule({ branch: branchId, min_income: rawIncome, percent: cleanPercent });
      toast.success("Threshold added.");
      setTouched(false);
      setDraft({ min_income: "", percent: "" });
      await onChanged();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to add threshold.");
    } finally {
      setBusy(false);
    }
  };

  const removeRule = async (rule) => {
    setPendingDelete(null);
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

    const items = branchRules(activeBranchId);

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
          <Button variant="secondary" size="sm" onClick={() => { setActiveBranchId(null); setComposing(false); setDraft({ min_income: "", percent: "" }); }}>
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
          {/* Delete confirmation modal */}
          <Modal
            isOpen={!!pendingDelete}
            onClose={() => setPendingDelete(null)}
            title="Delete threshold"
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <p style={{ margin: 0, fontSize: 14 }}>
                Remove the threshold starting at <strong>{fmtNum(pendingDelete?.min_income)} UZS</strong> ({pendingDelete?.percent}%)?
              </p>
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button type="button" onClick={() => setPendingDelete(null)}
                  style={{ padding: "10px 18px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", fontSize: 14, fontWeight: 600, fontFamily: "inherit", lineHeight: 1.4, transition: "background 150ms, border-color 150ms" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                >Cancel</button>
                <button type="button" disabled={busy} onClick={() => removeRule(pendingDelete)}
                  style={{ padding: "10px 18px", border: "1px solid var(--brand-danger)", borderRadius: "var(--radius-sm, 6px)", background: "var(--brand-danger)", cursor: "pointer", color: "#fff", fontSize: 14, fontWeight: 600, fontFamily: "inherit", lineHeight: 1.4, transition: "opacity 150ms" }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.85"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = "1"; }}
                >Delete</button>
              </div>
            </div>
          </Modal>

          <div style={{ marginBottom: 12 }}>
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
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                      background: "var(--bg-card, #fff)",
                      overflow: "hidden",
                    }}
                  >
                    {/* left accent bar */}
                    <div style={{ width: 4, alignSelf: "stretch", flexShrink: 0, background: "var(--brand-primary, #4338ca)" }} />

                    {/* income */}
                    <div style={{ flex: 1, padding: "10px 14px" }}>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 1 }}>Monthly income from</div>
                      <div style={{ fontWeight: 600, fontSize: 15 }}>{fmtNum(rule.min_income)} <span style={{ fontWeight: 400, fontSize: 12, color: "var(--text-muted)" }}>UZS</span></div>
                    </div>

                    {/* percent */}
                    <div style={{ padding: "10px 16px", fontWeight: 700, fontSize: 22, color: "var(--brand-primary, #4338ca)" }}>
                      {parseFloat(rule.percent)}<span style={{ fontSize: 14, fontWeight: 500 }}>%</span>
                    </div>

                    {/* trash button */}
                    <button
                      type="button"
                      onClick={() => setPendingDelete(rule)}
                      disabled={busy}
                      title="Remove"
                      style={{ padding: "0 14px", alignSelf: "stretch", background: "none", border: "none", borderLeft: "1px solid var(--border)", cursor: "pointer", fontSize: 15, transition: "background 150ms, color 150ms" }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--brand-primary)"; e.currentTarget.style.color = "#fff"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = ""; }}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="4" y1="6" x2="20" y2="6"/>
                        <rect x="7" y="6" width="10" height="14"/>
                        <line x1="10" y1="3" x2="14" y2="3"/>
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {composing ? (
            <form
              onSubmit={(e) => { e.preventDefault(); addRule(activeBranchId); }}
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
                  id="inc-min"
                  label="Threshold (UZS)"
                  type="text"
                  inputMode="numeric"
                  placeholder="e.g. 40 000 000"
                  value={draft.min_income}
                  className={touched && !toRaw(draft.min_income) ? "error" : ""}
                  onChange={(e) => {
                    const raw = toRaw(e.target.value).replace(/\D/g, "");
                    if (raw === "" || Number(raw) <= 9999999999)
                      setDraft((d) => ({ ...d, min_income: fmtInput(raw) }));
                  }}
                />
                <Input
                  id="inc-pct"
                  label="Percent"
                  type="text"
                  inputMode="decimal"
                  placeholder="5"
                  value={draft.percent}
                  className={touched && (!draft.percent || draft.percent.endsWith(".")) ? "error" : ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    const num = Number(v.replace(/\.$/, ""));
                    // block dot if integer part is 100, block >1 decimal, block >100
                    if (v === "" || (/^\d{1,3}(\.\d{0,1})?$/.test(v) && num <= 100 && !(v.includes(".") && num === 100)))
                      setDraft((d) => ({ ...d, percent: v }));
                  }}
                  onBlur={() => {
                    setDraft((d) => ({ ...d, percent: d.percent.replace(/\.$/, "") }));
                  }}
                />
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <button
                  type="submit"
                  disabled={busy}
                  title="Add"
                  style={{ padding: "6px 10px", height: 32, border: "1px solid var(--brand-primary)", borderRadius: "var(--radius-sm, 6px)", background: "var(--brand-primary)", cursor: "pointer", color: "#fff", display: "flex", alignItems: "center", transition: "opacity 150ms", boxSizing: "border-box" }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.85"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = "1"; }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                </button>
                <button
                  type="button"
                  disabled={busy}
                  title="Cancel"
                  onClick={() => { setComposing(false); setTouched(false); setDraft({ min_income: "", percent: "" }); }}
                  style={{ padding: "6px 10px", height: 32, border: "1px solid var(--border)", borderRadius: "var(--radius-sm, 6px)", background: "var(--bg-card)", cursor: "pointer", color: "var(--brand-primary)", display: "flex", alignItems: "center", transition: "background 150ms, border-color 150ms", boxSizing: "border-box" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-muted)"; e.currentTarget.style.borderColor = "var(--brand-primary)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-card)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setComposing(true)}
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
              <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Add
            </button>
          )}
        </div>
      </div>
    );
  }

  // ---------------- Branch list view ----------------
  return (
    <div className="card" style={{ marginTop: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>Income % thresholds</h3>
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
            const total = branchRules(branch.id).length;
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
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: 16,
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "var(--bg-card)",
                  cursor: "pointer",
                  textAlign: "left",
                  font: "inherit",
                  color: "inherit",
                  transition: "transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease",
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
                <div
                  style={{
                    width: 40, height: 40,
                    borderRadius: "var(--radius-sm, 8px)",
                    background: "var(--brand-primary)",
                    color: "var(--bg-card)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontWeight: 700, fontSize: 14, letterSpacing: 0.5, flexShrink: 0,
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
                <span className="text-muted" style={{ fontSize: 18, lineHeight: 1, marginLeft: 4 }} aria-hidden>›</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

IncomeRulesByBranch.propTypes = {
  branches: PropTypes.array.isRequired,
  rules: PropTypes.array.isRequired,
  onChanged: PropTypes.func.isRequired,
  activeBranchId: PropTypes.number,
};
