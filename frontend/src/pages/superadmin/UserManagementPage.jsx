import { useState, useEffect, useCallback, useMemo } from "react";
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
import Button from "../../components/Button";
import Input from "../../components/Input";
import Select from "../../components/Select";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
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

// Old-money palette — deep, low-chroma tones inspired by leather-bound
// libraries, hunter green, oxblood, and brass on cream stationery.
const ROLE_PILL_THEME = {
  superadmin:    { bg: "#ede1df", fg: "#5e1a14", border: "rgba(94,26,20,0.30)" },   // oxblood
  director:      { bg: "#e9e3d3", fg: "#6b5417", border: "rgba(107,84,23,0.30)" },  // brass / camel
  administrator: { bg: "#dde4e2", fg: "#1f3a36", border: "rgba(31,58,54,0.30)" },   // deep teal
  staff:         { bg: "#dfe6dc", fg: "#2a4327", border: "rgba(42,67,39,0.30)" },   // hunter green
  client:        { bg: "#e6e1d6", fg: "#4a3f2c", border: "rgba(74,63,44,0.30)" },   // taupe
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
  full_name_input: "",
  phone: "",
  password: "",
  branch: "",
  is_active: true,
  is_general_manager_input: false,
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

  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null); // null = create, object = edit
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (roleFilter) params.role = roleFilter;
      if (statusFilter) params.is_active = statusFilter;
      if (search) params.search = search;

      const [accountsData, branchesData] = await Promise.all([
        listAccounts(params),
        branches.length ? Promise.resolve(branches) : listBranches(),
      ]);
      // Client accounts are managed via the Bookings flow (walk-in / Telegram),
      // not from this internal staff directory.
      const internalOnly = (accountsData || []).filter(
        (acc) => acc.role && acc.role !== "client",
      );
      setAccounts(internalOnly);
      if (!branches.length) setBranches(branchesData);
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
  }, [roleFilter, statusFilter, search]);

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
    setEditing(account);
    setForm({
      role_input: primary,
      full_name_input: account.full_name || "",
      phone: account.phone || "",
      password: "",
      branch: account.branch_id ? String(account.branch_id) : "",
      is_active: account.is_active,
      is_general_manager_input: !!account.is_general_manager,
    });
    setFormError("");
    setModalOpen(true);
  };

  const validateCreate = () => {
    if (!form.phone.trim()) return "Phone is required.";
    if (!form.password || form.password.length < 6)
      return "Password must be at least 6 characters.";
    if (!form.full_name_input.trim()) return "Full name is required.";
    if (ROLES_NEEDING_BRANCH.has(form.role_input) && !form.branch)
      return "Branch is required for this role.";
    return "";
  };

  const buildCreatePayload = () => {
    const payload = {
      phone: form.phone.trim(),
      full_name_input: form.full_name_input.trim(),
      is_active: form.is_active,
      role_input: form.role_input,
      password: form.password,
    };
    if (ROLES_NEEDING_BRANCH.has(form.role_input)) {
      payload.branch = Number(form.branch);
    }
    if (form.role_input === "director") {
      payload.is_general_manager_input = !!form.is_general_manager_input;
    }
    return payload;
  };

  const buildUpdatePayload = () => {
    const payload = {
      phone: form.phone.trim(),
      full_name_input: form.full_name_input.trim(),
      is_active: form.is_active,
    };
    if (form.password) payload.password = form.password;
    if (editing?.role === "director") {
      payload.is_general_manager_input = !!form.is_general_manager_input;
    }
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
  // Table definition
  // ---------------------------------------------------------------------
  const columns = useMemo(
    () => [
      { key: "full_name", label: "Name", render: (val) => val || <em className="text-muted">—</em> },
      { key: "phone", label: "Phone", render: (val) => val || <em className="text-muted">—</em> },
      {
        key: "role",
        label: "Role",
        render: (val) =>
          val ? (
            <span style={rolePillStyle(val)}>
              {ROLE_LABEL[val] || val}
            </span>
          ) : (
            <em className="text-muted">none</em>
          ),
      },
      {
        key: "branch_name",
        label: "Branch",
        render: (val) => val || <em className="text-muted">—</em>,
      },
      {
        key: "is_active",
        label: "Status",
        render: (val) => (
          <span className={`badge ${val ? "badge-success" : "badge-muted"}`}>
            {val ? "Active" : "Disabled"}
          </span>
        ),
      },
      {
        key: "_actions",
        label: "",
        render: (_, row) => (
          <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
            <Button
              variant="secondary"
              size="sm"
              disabled={busyId === row.id}
              onClick={(e) => {
                e.stopPropagation();
                openEdit(row);
              }}
            >
              Edit
            </Button>
            <Button
              variant={row.is_active ? "warning" : "success"}
              size="sm"
              disabled={busyId === row.id || row.id === user?.id}
              onClick={(e) => {
                e.stopPropagation();
                handleToggleActive(row);
              }}
            >
              {row.is_active ? "Disable" : "Enable"}
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={busyId === row.id || row.id === user?.id}
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(row);
              }}
            >
              Delete
            </Button>
          </div>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busyId, user?.id]
  );

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
        <Button variant="primary" onClick={openCreate}>
          + Add User
        </Button>
      </div>

      {/* Filters */}
      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          marginBottom: 16,
          alignItems: "flex-end",
        }}
      >
        <div className="form-group" style={{ minWidth: 180 }}>
          <label className="label" htmlFor="role-filter">Role</label>
          <Select
            id="role-filter"
            value={roleFilter}
            onChange={(v) => setRoleFilter(v)}
            placeholder="All roles"
            options={[
              { value: "", label: "All roles" },
              ...ROLE_OPTIONS,
              { value: "client", label: "Client" },
            ]}
          />
        </div>
        <div className="form-group" style={{ minWidth: 150 }}>
          <label className="label" htmlFor="status-filter">Status</label>
          <Select
            id="status-filter"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v)}
            placeholder="All"
            options={[
              { value: "", label: "All" },
              { value: "true", label: "Active" },
              { value: "false", label: "Disabled" },
            ]}
          />
        </div>
        <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
          <label className="label" htmlFor="user-search">Search</label>
          <input
            id="user-search"
            className="input"
            placeholder="Phone or telegram id"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {error && <ErrorMessage message={error} onRetry={fetchAll} />}

      <Table columns={columns} data={accounts} emptyMessage="No accounts found." />

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
            label="Full Name"
            required
            value={form.full_name_input}
            onChange={(e) => setForm({ ...form, full_name_input: e.target.value })}
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

          {/* General Manager checkbox — Director-only.
              GM directors get extra salary bonuses + a personal yearly Excel
              workbook (visible only to them and the CEO). */}
          {((!editing && form.role_input === "director") ||
            editing?.role === "director") && (
            <div className="form-group">
              <label
                className="label"
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <input
                  type="checkbox"
                  checked={!!form.is_general_manager_input}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      is_general_manager_input: e.target.checked,
                    })
                  }
                  disabled={saving}
                />
                <span>
                  Acts as General Manager (Бош менеджер — extra bonus + personal
                  yearly report)
                </span>
              </label>
            </div>
          )}

          {editing && (
            <div className="form-group">
              <label
                className="label"
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  disabled={saving}
                />
                <span>Account is active</span>
              </label>
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
