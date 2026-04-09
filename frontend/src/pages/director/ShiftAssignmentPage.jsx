import { useState, useEffect, useCallback } from "react";
import { getShifts, createShift } from "../../services/shiftService";
import ShiftForm from "../../components/ShiftForm";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const SHIFT_LABELS = {
  day: "☀️ Day",
  night: "🌙 Night",
};

const columns = [
  {
    key: "account_name",
    label: "User",
    render: (val, row) => val || row.account_full_name || `#${row.account}`,
  },
  {
    key: "role",
    label: "Role",
    render: (val, row) => {
      const roles = row.account_roles || [];
      if (roles.includes("administrator")) return "Admin";
      if (roles.includes("staff")) return "Staff";
      return roles[0] || "—";
    },
  },
  {
    key: "branch_name",
    label: "Branch",
    render: (val, row) => val || `Branch #${row.branch}`,
  },
  {
    key: "shift_type",
    label: "Shift",
    render: (val) => SHIFT_LABELS[val] || val,
  },
  {
    key: "date",
    label: "Date",
  },
];

function ShiftAssignmentPage() {
  const [shifts, setShifts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  const fetchShifts = useCallback(async () => {
    try {
      setError(null);
      const data = await getShifts({ ordering: "-date" });
      const list = data.results ?? data;
      setShifts(list);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load shifts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchShifts();
  }, [fetchShifts]);

  const handleCreate = async (formData) => {
    try {
      setSubmitLoading(true);
      setError(null);
      setSuccessMsg("");
      await createShift(formData);
      setSuccessMsg("Shift assigned successfully!");
      await fetchShifts();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err) {
      const data = err.response?.data;
      const msg =
        data?.detail ||
        data?.non_field_errors?.[0] ||
        (typeof data === "object" ? Object.values(data).flat().join(". ") : "Failed to assign shift");
      setError(msg);
    } finally {
      setSubmitLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ margin: "0 0 20px" }}>📅 Shift Assignments</h2>

      {/* Form section */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 20,
          marginBottom: 24,
          maxWidth: 480,
        }}
      >
        <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600 }}>
          Assign New Shift
        </h3>
        <ShiftForm
          onSubmit={handleCreate}
          loading={submitLoading}
          existingShifts={shifts}
        />
      </div>

      {/* Success message */}
      {successMsg && (
        <div
          style={{
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: 6,
            padding: "8px 12px",
            marginBottom: 16,
            fontSize: 13,
            color: "#166534",
          }}
        >
          ✅ {successMsg}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div style={{ marginBottom: 16 }}>
          <ErrorMessage message={error} />
        </div>
      )}

      {/* Table */}
      {loading ? (
        <Loader />
      ) : (
        <Table columns={columns} data={shifts} emptyMessage="No shift assignments yet" />
      )}
    </div>
  );
}

export default ShiftAssignmentPage;
