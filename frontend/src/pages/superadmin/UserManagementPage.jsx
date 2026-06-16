import { useState, useEffect, useCallback } from "react";
import {
  listAccounts,
  createAccount,
  updateAccount,
  deleteAccount,
  disableAccount,
  enableAccount,
  listBranches,
  listBranchesAvailableForDirector,
} from "../../services/accountsService";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useBranchScope } from "../../context/BranchScopeContext";
import usePersistedBranch from "../../hooks/usePersistedBranch";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Select from "../../components/Select";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const ROLE_OPTIONS = [
  { value: "staff", label: "Staff (Cleaner)" },
  { value: "administrator", label: "Administrator" },
  { value: "director", label: "Director" },
  { value: "superadmin", label: "CEO" },
];
const ROLE_LABEL = Object.fromEntries(ROLE_OPTIONS.map((r) => [r.value, r.label]));
const ROLES_NEEDING_BRANCH = new Set(["staff", "administrator", "director"]);

// Elegant per-role pill — muted tints, single shared shape.
const ROLE_PILL_BASE = {
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 0.4,
  textTransform: "uppercase",
  border: "1px solid",
};

// Refined role-pill palette — clean, distinct, professional
const ROLE_PILL_THEME = {
  superadmin:    { bg: "#eae8f5", fg: "#3b2f8a", border: "rgba(59,47,138,0.22)" },  // royal indigo
  director:      { bg: "#fef4e4", fg: "#854d00", border: "rgba(133,77,0,0.22)" },   // rich amber
  administrator: { bg: "#e2f0f4", fg: "#0d5c6c", border: "rgba(13,92,108,0.22)" }, // ocean teal
  staff:         { bg: "#e8f4e8", fg: "#2a6b2a", border: "rgba(42,107,42,0.22)" }, // clean green
  client:        { bg: "#edeef4", fg: "#3a4060", border: "rgba(58,64,96,0.22)" },  // slate blue
};

function rolePillStyle(role) {
  const theme = ROLE_PILL_THEME[role] || ROLE_PILL_THEME.client;
  return {
    ...ROLE_PILL_BASE,
    background: theme.bg,
    color: theme.fg,
    borderColor: theme.border,
  };
}

const EMPTY_FORM = {
  role_input: "staff",
  first_name: "",
  last_name: "",
  phone: "",
  password: "",
  confirm_password: "",
  branch: "",
  is_active: true,
};

function getSubmitLabel(saving, editing) {
  if (saving) return "Saving…";
  return editing ? "Save Changes" : "Create Account";
}

function UserManagementPage() {
  const { user } = useAuth();
  const toast = useToast();

  const [accounts, setAccounts] = useState([]);
  const [branches, setBranches] = useState([]);
  const [directorBranches, setDirectorBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [branchId, setBranchId] = usePersistedBranch(
    "branchScope:userManagement", true, null,
  );

  // Register branch scope in the global fixed header
  const { register, unregister } = useBranchScope();
  useEffect(() => { register(branchId, setBranchId); }, [branchId, register, setBranchId]);
  useEffect(() => () => unregister(), [unregister]);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null); // null = create, object = edit
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);
  // CEO accounts have no branch so we show them separately when a branch
  // filter is active — they would otherwise be hidden by the branch param.
  const [ceoAccounts, setCeoAccounts] = useState([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (branchId) params.branch = branchId;

      const [accountsData, branchesData] = await Promise.all([
        listAccounts(params),
        branches.length ? Promise.resolve(branches) : listBranches(),
      ]);
      // Client accounts are managed via the Bookings flow (walk-in / Telegram),
      // not from this internal staff directory.
      const internalOnly = (accountsData || []).filter(
        (acc) => acc.role && acc.role !== "client",
      );
      // When scoped to a branch, surface CEO accounts separately and avoid
      // showing them twice by excluding `superadmin` from the main list.
      if (branchId) setAccounts(internalOnly.filter((a) => a.role !== "superadmin"));
      else setAccounts(internalOnly);
      if (!branches.length) setBranches(branchesData);

      // When scoped to a branch, also surface CEO accounts (no branch FK).
      if (branchId) {
        try {
          const ceoData = await listAccounts({ role: "superadmin" });
          setCeoAccounts((ceoData || []).filter((a) => a.role === "superadmin"));
        } catch {
          setCeoAccounts([]);
        }
      } else {
        setCeoAccounts([]);
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.response?.data?.error?.message ||
          "Failed to load accounts."
      );
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branchId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // When the create modal switches to "Director" role, fetch the up-to-date
  // list of branches that don't already have an active director. We refetch
  // every time the modal opens so a recently-deleted director doesn't keep
  // their branch hidden.
  useEffect(() => {
    if (!modalOpen || editing) return;
    if (form.role_input !== "director") return;
    let cancelled = false;
    listBranchesAvailableForDirector()
      .then((data) => {
        if (!cancelled) setDirectorBranches(data || []);
      })
      .catch(() => {
        if (!cancelled) setDirectorBranches([]);
      });
    return () => {
      cancelled = true;
    };
  }, [modalOpen, editing, form.role_input]);

  // ---------------------------------------------------------------------
  // Modal handling
  // ---------------------------------------------------------------------
  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError("");
    setModalOpen(true);
  };

  const openEdit = (account) => {
    const primary = account.role || "staff";
    const [firstName = "", ...rest] = (account.full_name || "").trim().split(/\s+/);
    setEditing(account);
    setForm({
      role_input: primary,
      first_name: firstName,
      last_name: rest.join(" "),
      phone: account.phone || "",
      password: "",
      confirm_password: "",
      branch: account.branch_id ? String(account.branch_id) : "",
      is_active: account.is_active,
    });
    setFormError("");
    setModalOpen(true);
  };

  const validateCreate = () => {
    const phone = form.phone.trim();
    if (!phone) return "Phone is required.";
    if (!/^\+?[1-9]\d{7,14}$/.test(phone.replace(/[\s\-()+]/g, "")))
      return "Phone must be in E.164 format, e.g. +998901234567.";
    const firstName = form.first_name.trim();
    const lastName = form.last_name.trim();
    if (!firstName || firstName.length < 2)
      return "First name must be at least 2 characters.";
    if (!lastName || lastName.length < 2)
      return "Last name must be at least 2 characters.";
    if (!form.password || form.password.length < 6)
      return "Password must be at least 6 characters.";
    if (!form.confirm_password) return "Please confirm the password.";
    if (form.password !== form.confirm_password) return "Passwords do not match.";
    if (ROLES_NEEDING_BRANCH.has(form.role_input) && !form.branch)
      return "Branch is required for this role.";
    return "";
  };

  const buildCreatePayload = () => {
    const payload = {
      phone: form.phone.trim(),
      full_name_input: `${form.first_name.trim()} ${form.last_name.trim()}`.trim(),
      is_active: form.is_active,
      role_input: form.role_input,
      password: form.password,
      confirm_password: form.confirm_password,
    };
    if (ROLES_NEEDING_BRANCH.has(form.role_input)) {
      payload.branch = Number(form.branch);
    }
    return payload;
  };

  const buildUpdatePayload = () => {
    const payload = {
      phone: form.phone.trim(),
      full_name_input: `${form.first_name.trim()} ${form.last_name.trim()}`.trim(),
      is_active: form.is_active,
    };
    if (form.password) payload.password = form.password;
    return payload;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError("");

    if (editing === null) {
      const validationError = validateCreate();
      if (validationError) {
        setFormError(validationError);
        return;
      }
    }

    const payload = editing ? buildUpdatePayload() : buildCreatePayload();

    setSaving(true);
    try {
      if (editing) {
        await updateAccount(editing.id, payload);
        toast.success("Account updated.");
      } else {
        await createAccount(payload);
        toast.success("Account created.");
      }
      setModalOpen(false);
      fetchAll();
    } catch (err) {
      const data = err.response?.data;
      const detail =
        data?.error?.message ||
        data?.detail ||
        (typeof data === "object" ? Object.values(data).flat().join(" ") : null) ||
        "Failed to save account.";
      setFormError(detail);
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------------------
  // Row actions
  // ---------------------------------------------------------------------
  const handleToggleActive = async (account) => {
    if (account.id === user?.id) {
      toast.warning("You cannot disable your own account.");
      return;
    }
    setBusyId(account.id);
    try {
      if (account.is_active) {
        await disableAccount(account.id);
        toast.success(`${account.full_name || "Account"} disabled.`);
      } else {
        await enableAccount(account.id);
        toast.success(`${account.full_name || "Account"} enabled.`);
      }
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update account.");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (account) => {
    if (account.id === user?.id) {
      toast.warning("You cannot delete your own account.");
      return;
    }
    const ok = globalThis.confirm(
      `Permanently delete ${account.full_name || account.phone || "this account"}? This cannot be undone.`
    );
    if (!ok) return;

    setBusyId(account.id);
    try {
      await deleteAccount(account.id);
      toast.success("Account deleted.");
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete.");
    } finally {
      setBusyId(null);
    }
  };

  // ---------------------------------------------------------------------
  // User row renderer
  // ---------------------------------------------------------------------
  const renderUserRow = (acc) => {
    const initial = (acc.full_name || acc.phone || "?").trim().charAt(0).toUpperCase();
    const isSelf = acc.id === user?.id;
    return (
      <tr key={acc.id}>
        <td>
          <div className="user-cell">
            <span className="user-cell__avatar">{initial}</span>
            <div className="user-cell__id">
              <span className="user-cell__name">
                {acc.full_name || <em className="text-muted">Unnamed</em>}
              </span>
              <span className="user-cell__phone">{acc.phone || "—"}</span>
            </div>
          </div>
        </td>
        <td>
          {acc.role ? (
            <span style={rolePillStyle(acc.role)}>{ROLE_LABEL[acc.role] || acc.role}</span>
          ) : (
            <span className="text-muted">—</span>
          )}
        </td>
        <td className="user-cell__branch">
          {acc.branch_name || <span className="text-muted">—</span>}
        </td>
        <td>
          <span className={`user-pill-status ${acc.is_active ? "is-active" : "is-disabled"}`}>
            {acc.is_active ? "Active" : "Disabled"}
          </span>
        </td>
        <td>
          <div className="user-row-actions">
            <Button
              variant="secondary"
              size="sm"
              disabled={busyId === acc.id}
              onClick={() => openEdit(acc)}
            >
              Edit
            </Button>
            <Button
              variant={acc.is_active ? "warning" : "success"}
              size="sm"
              disabled={busyId === acc.id || isSelf}
              onClick={() => handleToggleActive(acc)}
            >
              {acc.is_active ? "Disable" : "Enable"}
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={busyId === acc.id || isSelf}
              onClick={() => handleDelete(acc)}
            >
              Delete
            </Button>
          </div>
        </td>
      </tr>
    );
  };

  // ---------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------
  if (loading && accounts.length === 0) return <Loader message="Loading accounts..." />;

  return (
    <div>
      <div
        className="page-header"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        <h1>Users &amp; Roles</h1>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Button variant="primary" onClick={openCreate}>
            + Add User
          </Button>
        </div>
      </div>

      {error && <ErrorMessage message={error} onRetry={fetchAll} />}

      {accounts.length === 0 && ceoAccounts.length === 0 ? (
        <div className="empty-state">No accounts found.</div>
      ) : (
        <div className="user-table-wrap">
          <table className="user-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Branch</th>
                <th>Status</th>
                <th className="user-table__actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(renderUserRow)}
              {branchId && ceoAccounts.length > 0 && (
                <>
                  {accounts.length > 0 && (
                    <tr className="user-table__sep" aria-hidden="true">
                      <td colSpan={5} />
                    </tr>
                  )}
                  {ceoAccounts.map(renderUserRow)}
                </>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => !saving && setModalOpen(false)}
        title={editing ? `Edit Account — ${editing.full_name || editing.phone}` : "Create Account"}
      >
        <form onSubmit={handleSubmit}>
          {!editing && (
            <div className="form-group">
              <label className="label" htmlFor="role-input">
                Role <span className="text-accent">*</span>
              </label>
              <Select
                id="role-input"
                value={form.role_input}
                onChange={(v) => setForm({ ...form, role_input: v })}
                options={ROLE_OPTIONS}
                disabled={saving}
              />
            </div>
          )}

          <Input
            label="First Name"
            required
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            disabled={saving}
          />

          <Input
            label="Last Name"
            required
            value={form.last_name}
            onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            disabled={saving}
          />

          <Input
            label="Phone"
            required={!editing}
            placeholder="+998..."
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            disabled={saving}
          />

          <Input
            label={editing ? "New Password (leave blank to keep current)" : "Password"}
            type="password"
            required={!editing}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            disabled={saving}
          />

          {!editing && (
            <Input
              label="Confirm Password"
              type="password"
              required
              value={form.confirm_password}
              onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
              disabled={saving}
            />
          )}

          {!editing && ROLES_NEEDING_BRANCH.has(form.role_input) && (
            <div className="form-group">
              <label className="label" htmlFor="branch-input">
                Branch <span className="text-accent">*</span>
              </label>
              <Select
                id="branch-input"
                value={form.branch}
                onChange={(v) => setForm({ ...form, branch: v })}
                placeholder="— Select branch —"
                options={(form.role_input === "director"
                  ? directorBranches
                  : branches
                ).map((b) => ({ value: b.id, label: b.name }))}
                disabled={saving}
                emptyText={
                  form.role_input === "director"
                    ? "Every branch already has an active director."
                    : "No branches available"
                }
              />
              {form.role_input === "director" && (
                <p className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                  Only branches without an active director are listed (one
                  director per branch).
                </p>
              )}
            </div>
          )}

          {formError && (
            <div className="alert alert-danger" style={{ marginBottom: 12 }}>
              {formError}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button
              variant="secondary"
              type="button"
              onClick={() => setModalOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={saving}>
              {getSubmitLabel(saving, editing)}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default UserManagementPage;
