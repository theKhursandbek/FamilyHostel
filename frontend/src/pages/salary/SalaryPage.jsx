import { useState, useEffect, useCallback } from "react";
import { getSalaries } from "../../services/salaryService";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const STATUS_COLORS = {
  paid: "#22c55e",
  pending: "#f59e0b",
};

const columns = [
  {
    key: "account_name",
    label: "User",
    render: (val, row) => val || row.full_name || `#${row.account || row.id}`,
  },
  {
    key: "total_salary",
    label: "Total Salary",
    render: (val) =>
      val !== null && val !== undefined
        ? `${Number(val).toLocaleString()} сум`
        : "—",
  },
  {
    key: "period",
    label: "Period",
    render: (val, row) => {
      if (val) return val;
      if (row.period_start && row.period_end) {
        return `${row.period_start} — ${row.period_end}`;
      }
      if (row.month && row.year) {
        return `${row.month}/${row.year}`;
      }
      return "—";
    },
  },
  {
    key: "status",
    label: "Status",
    render: (val) => (
      <span
        style={{
          display: "inline-block",
          padding: "2px 10px",
          borderRadius: 12,
          fontSize: 12,
          fontWeight: 600,
          color: "#fff",
          backgroundColor: STATUS_COLORS[val] || "#6b7280",
        }}
      >
        {val ? val.charAt(0).toUpperCase() + val.slice(1) : "—"}
      </span>
    ),
  },
];

function SalaryPage() {
  const [salaries, setSalaries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSalaries = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getSalaries();
      const list = data.results ?? data;
      setSalaries(list);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load salary records");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSalaries();
  }, [fetchSalaries]);

  return (
    <div>
      <h2 style={{ margin: "0 0 20px" }}>💰 Salary Records</h2>

      {error && (
        <div style={{ marginBottom: 16 }}>
          <ErrorMessage message={error} onRetry={fetchSalaries} />
        </div>
      )}

      {loading ? (
        <Loader />
      ) : (
        <Table
          columns={columns}
          data={salaries}
          emptyMessage="No salary records found"
        />
      )}
    </div>
  );
}

export default SalaryPage;
