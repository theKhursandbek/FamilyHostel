import { useState, useEffect, useCallback } from "react";
import { getShifts, createShift } from "../../services/shiftService";
import { useToast } from "../../context/ToastContext";
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
  const toast = useToast();
  const [shifts, setShifts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitLoading, setSubmitLoading] = useState(false);

  const fetchShifts = useCallback(async () => {
    try {
      setLoading(true);
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
      await createShift(formData);
      toast.success("Shift assigned successfully!");
      await fetchShifts();
    } catch (err) {
      const data = err.response?.data;
      const msg =
        data?.detail ||
        data?.non_field_errors?.[0] ||
        (typeof data === "object" ? Object.values(data).flat().join(". ") : "Failed to assign shift");
      toast.error(msg);
    } finally {
      setSubmitLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header"><h1>📅 Shift Assignments</h1></div>

      {/* Form section */}
      <div className="card" style={{ maxWidth: 480 }}>
        <h3 className="section-title">
          Assign New Shift
        </h3>
        <ShiftForm
          onSubmit={handleCreate}
          loading={submitLoading}
          existingShifts={shifts}
        />
      </div>

      {/* Error message */}
      {error && (
        <div style={{ marginBottom: 16 }}>
          <ErrorMessage message={error} onRetry={fetchShifts} />
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
