import { useState, useEffect } from "react";
import { getAccounts, getBranches } from "../services/shiftService";
import { useToast } from "../context/ToastContext";
import Input from "./Input";
import Button from "./Button";

function ShiftForm({ onSubmit, loading = false, existingShifts = [] }) {
  const toast = useToast();
  const [accounts, setAccounts] = useState([]);
  const [branches, setBranches] = useState([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [form, setForm] = useState({
    account: "",
    role: "staff",
    branch: "",
    shift_type: "day",
    date: "",
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    async function fetchData() {
      try {
        const [accountsData, branchesData] = await Promise.all([
          getAccounts(),
          getBranches(),
        ]);
        const accountList = accountsData.results ?? accountsData;
        const branchList = branchesData.results ?? branchesData;
        setAccounts(accountList);
        setBranches(branchList);
      } catch {
        setAccounts([]);
        setBranches([]);
        toast.error("Failed to load accounts and branches");
      } finally {
        setDataLoading(false);
      }
    }
    fetchData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Filter accounts by selected role
  const filteredAccounts = accounts.filter((acc) => {
    const roles = acc.roles || [];
    if (form.role === "staff") return roles.includes("staff");
    if (form.role === "admin") return roles.includes("administrator");
    return true;
  });

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setErrors((prev) => ({ ...prev, [field]: "", general: "" }));
  };

  const checkDuplicate = () => {
    return existingShifts.some(
      (s) =>
        String(s.account) === String(form.account) &&
        s.date === form.date &&
        s.shift_type === form.shift_type
    );
  };

  const checkAdminConflict = () => {
    if (form.role !== "admin") return false;
    return existingShifts.some(
      (s) =>
        s.date === form.date &&
        s.shift_type === form.shift_type &&
        String(s.branch) === String(form.branch) &&
        s.role === "admin" &&
        String(s.account) !== String(form.account)
    );
  };

  const validate = () => {
    const newErrors = {};
    if (!form.account) newErrors.account = "Account is required";
    if (!form.branch) newErrors.branch = "Branch is required";
    if (!form.date) newErrors.date = "Date is required";

    if (!newErrors.account && !newErrors.date && checkDuplicate()) {
      newErrors.general = "This person is already assigned to this shift on this date";
    }

    if (!newErrors.account && !newErrors.date && !newErrors.branch && checkAdminConflict()) {
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
      branch: Number(form.branch),
      shift_type: form.shift_type,
      date: form.date,
    });
  };

  const handleReset = () => {
    setForm({ account: "", role: "staff", branch: "", shift_type: "day", date: "" });
    setErrors({});
  };

  return (
    <form onSubmit={handleSubmit}>
      {errors.general && (
        <div className="alert alert-warning">
          ⚠️ {errors.general}
        </div>
      )}

      {/* Role selector */}
      <div className="form-group">
        <label htmlFor="role" className="label">
          Role <span style={{ color: "var(--danger)" }}>*</span>
        </label>
        <select
          id="role"
          value={form.role}
          onChange={(e) => {
            setForm((prev) => ({ ...prev, role: e.target.value, account: "" }));
            setErrors((prev) => ({ ...prev, account: "", general: "" }));
          }}
          className="select"
        >
          <option value="staff">Staff</option>
          <option value="admin">Admin</option>
        </select>
      </div>

      {/* Account selector */}
      <div className="form-group">
        <label htmlFor="account" className="label">
          Account <span style={{ color: "var(--danger)" }}>*</span>
        </label>
        <select
          id="account"
          value={form.account}
          onChange={handleChange("account")}
          disabled={dataLoading}
          className={`select${errors.account ? " error" : ""}`}
        >
          <option value="">
            {dataLoading ? "Loading..." : "Select account"}
          </option>
          {filteredAccounts.map((acc) => (
            <option key={acc.id} value={acc.id}>
              {acc.full_name || acc.phone || `Account #${acc.id}`}
            </option>
          ))}
        </select>
        {errors.account && (
          <p className="form-error">{errors.account}</p>
        )}
      </div>

      {/* Branch selector */}
      <div className="form-group">
        <label htmlFor="branch" className="label">
          Branch <span style={{ color: "var(--danger)" }}>*</span>
        </label>
        <select
          id="branch"
          value={form.branch}
          onChange={handleChange("branch")}
          disabled={dataLoading}
          className={`select${errors.branch ? " error" : ""}`}
        >
          <option value="">
            {dataLoading ? "Loading..." : "Select branch"}
          </option>
          {branches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name || `Branch #${b.id}`}
            </option>
          ))}
        </select>
        {errors.branch && (
          <p className="form-error">{errors.branch}</p>
        )}
      </div>

      {/* Shift type */}
      <div className="form-group">
        <label htmlFor="shift_type" className="label">
          Shift Type <span style={{ color: "var(--danger)" }}>*</span>
        </label>
        <select
          id="shift_type"
          value={form.shift_type}
          onChange={handleChange("shift_type")}
          className="select"
        >
          <option value="day">Day</option>
          <option value="night">Night</option>
        </select>
      </div>

      {/* Date */}
      <Input
        label="Date"
        id="date"
        type="date"
        value={form.date}
        onChange={handleChange("date")}
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

export default ShiftForm;
