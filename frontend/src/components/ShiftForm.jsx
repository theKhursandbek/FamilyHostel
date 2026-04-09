import { useState, useEffect } from "react";
import { getAccounts, getBranches } from "../services/shiftService";
import Input from "./Input";
import Button from "./Button";

function ShiftForm({ onSubmit, loading = false, existingShifts = [] }) {
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
      } finally {
        setDataLoading(false);
      }
    }
    fetchData();
  }, []);

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
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            padding: "8px 12px",
            marginBottom: 12,
            fontSize: 13,
            color: "#991b1b",
          }}
        >
          ⚠️ {errors.general}
        </div>
      )}

      {/* Role selector */}
      <div style={{ marginBottom: 16 }}>
        <label
          htmlFor="role"
          style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}
        >
          Role <span style={{ color: "#dc2626" }}>*</span>
        </label>
        <select
          id="role"
          value={form.role}
          onChange={(e) => {
            setForm((prev) => ({ ...prev, role: e.target.value, account: "" }));
            setErrors((prev) => ({ ...prev, account: "", general: "" }));
          }}
          style={{
            width: "100%",
            padding: 8,
            border: "1px solid #dadce0",
            borderRadius: 4,
            fontSize: 14,
            boxSizing: "border-box",
          }}
        >
          <option value="staff">Staff</option>
          <option value="admin">Admin</option>
        </select>
      </div>

      {/* Account selector */}
      <div style={{ marginBottom: 16 }}>
        <label
          htmlFor="account"
          style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}
        >
          Account <span style={{ color: "#dc2626" }}>*</span>
        </label>
        <select
          id="account"
          value={form.account}
          onChange={handleChange("account")}
          disabled={dataLoading}
          style={{
            width: "100%",
            padding: 8,
            border: `1px solid ${errors.account ? "#dc2626" : "#dadce0"}`,
            borderRadius: 4,
            fontSize: 14,
            boxSizing: "border-box",
          }}
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
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#dc2626" }}>{errors.account}</p>
        )}
      </div>

      {/* Branch selector */}
      <div style={{ marginBottom: 16 }}>
        <label
          htmlFor="branch"
          style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}
        >
          Branch <span style={{ color: "#dc2626" }}>*</span>
        </label>
        <select
          id="branch"
          value={form.branch}
          onChange={handleChange("branch")}
          disabled={dataLoading}
          style={{
            width: "100%",
            padding: 8,
            border: `1px solid ${errors.branch ? "#dc2626" : "#dadce0"}`,
            borderRadius: 4,
            fontSize: 14,
            boxSizing: "border-box",
          }}
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
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#dc2626" }}>{errors.branch}</p>
        )}
      </div>

      {/* Shift type */}
      <div style={{ marginBottom: 16 }}>
        <label
          htmlFor="shift_type"
          style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}
        >
          Shift Type <span style={{ color: "#dc2626" }}>*</span>
        </label>
        <select
          id="shift_type"
          value={form.shift_type}
          onChange={handleChange("shift_type")}
          style={{
            width: "100%",
            padding: 8,
            border: "1px solid #dadce0",
            borderRadius: 4,
            fontSize: 14,
            boxSizing: "border-box",
          }}
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

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
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
