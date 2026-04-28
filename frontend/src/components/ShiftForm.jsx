import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { getAccounts } from "../services/shiftService";
import { useToast } from "../context/ToastContext";
import Input from "./Input";
import Button from "./Button";
import Select from "./Select";

function toListArray(d) {
  if (Array.isArray(d)) return d;
  if (Array.isArray(d?.results)) return d.results;
  if (Array.isArray(d?.data)) return d.data;
  return [];
}

const ROLE_OPTIONS = [
  { value: "staff", label: "Staff" },
  { value: "admin", label: "Admin" },
];

const SHIFT_TYPE_OPTIONS = [
  { value: "day", label: "Day" },
  { value: "night", label: "Night" },
];

function ShiftForm({ onSubmit, loading = false, existingShifts = [] }) {
  const toast = useToast();
  const [accounts, setAccounts] = useState([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [form, setForm] = useState({
    account: "",
    role: "staff",
    shift_type: "day",
    date: "",
  });
  const [errors, setErrors] = useState({});

  const fetchData = useCallback(async () => {
    setDataLoading(true);
    setLoadError(false);
    try {
      const accountsData = await getAccounts();
      setAccounts(toListArray(accountsData));
    } catch {
      setAccounts([]);
      setLoadError(true);
      toast.error("Failed to load accounts");
    } finally {
      setDataLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredAccounts = accounts.filter((acc) => {
    const roles = acc.roles || [];
    if (form.role === "staff") return roles.includes("staff");
    if (form.role === "admin") return roles.includes("administrator");
    return true;
  });

  const accountOptions = filteredAccounts.map((acc) => ({
    value: acc.id,
    label: acc.full_name || acc.phone || `Account #${acc.id}`,
  }));

  const selectedAccount = accounts.find(
    (a) => String(a.id) === String(form.account),
  );
  const derivedBranchId = selectedAccount?.branch_id ?? null;

  const setField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "", general: "" }));
  };

  const checkDuplicate = () =>
    existingShifts.some(
      (s) =>
        String(s.account) === String(form.account) &&
        s.date === form.date &&
        s.shift_type === form.shift_type
    );

  const checkAdminConflict = () => {
    if (form.role !== "admin") return false;
    return existingShifts.some(
      (s) =>
        s.date === form.date &&
        s.shift_type === form.shift_type &&
        String(s.branch) === String(derivedBranchId) &&
        s.role === "admin" &&
        String(s.account) !== String(form.account)
    );
  };

  const validate = () => {
    const newErrors = {};
    if (!form.account) newErrors.account = "Account is required";
    if (!derivedBranchId)
      newErrors.account = "Selected account has no branch assigned";
    if (!form.date) newErrors.date = "Date is required";

    if (!newErrors.account && !newErrors.date && checkDuplicate()) {
      newErrors.general = "This person is already assigned to this shift on this date";
    }

    if (!newErrors.account && !newErrors.date && checkAdminConflict()) {
      newErrors.general = "Another admin is already assigned to this shift at this branch";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({
      account: Number(form.account),
      role: form.role,
      branch: Number(derivedBranchId),
      shift_type: form.shift_type,
      date: form.date,
    });
  };

  const handleReset = () => {
    setForm({ account: "", role: "staff", shift_type: "day", date: "" });
    setErrors({});
  };

  return (
    <form onSubmit={handleSubmit}>
      {errors.general && (
        <div className="alert alert-warning">{errors.general}</div>
      )}

      {loadError && (
        <div
          className="alert alert-error"
          style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
        >
          <span>Could not load accounts &amp; branches. Check your connection.</span>
          <Button type="button" variant="ghost" onClick={fetchData} disabled={dataLoading}>
            Retry
          </Button>
        </div>
      )}

      <div className="form-group">
        <label htmlFor="role" className="label">
          Role <span style={{ color: "var(--brand-danger)" }}>*</span>
        </label>
        <Select
          id="role"
          value={form.role}
          onChange={(v) => {
            setForm((prev) => ({ ...prev, role: v, account: "" }));
            setErrors((prev) => ({ ...prev, account: "", general: "" }));
          }}
          options={ROLE_OPTIONS}
        />
      </div>

      <div className="form-group">
        <label htmlFor="account" className="label">
          Account <span style={{ color: "var(--brand-danger)" }}>*</span>
        </label>
        <Select
          id="account"
          value={form.account}
          onChange={(v) => setField("account", v)}
          options={accountOptions}
          loading={dataLoading}
          disabled={loadError && !dataLoading}
          placeholder={loadError ? "Unavailable — retry above" : "Select account"}
          emptyText={
            form.role === "staff" ? "No staff accounts found" : "No admin accounts found"
          }
          error={Boolean(errors.account)}
        />
        {errors.account && <p className="form-error">{errors.account}</p>}
      </div>

      <div className="form-group">
        <label htmlFor="shift_type" className="label">
          Shift Type <span style={{ color: "var(--brand-danger)" }}>*</span>
        </label>
        <Select
          id="shift_type"
          value={form.shift_type}
          onChange={(v) => setField("shift_type", v)}
          options={SHIFT_TYPE_OPTIONS}
        />
      </div>

      <Input
        label="Date"
        id="date"
        type="date"
        value={form.date}
        onChange={(e) => setField("date", e.target.value)}
        required
        error={errors.date}
      />

      <div className="form-actions">
        <Button type="button" variant="ghost" onClick={handleReset} disabled={loading}>
          Reset
        </Button>
        <Button type="submit" disabled={loading}>
          {loading ? "Assigning..." : "Assign Shift"}
        </Button>
      </div>
    </form>
  );
}

ShiftForm.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  existingShifts: PropTypes.array,
};

export default ShiftForm;
