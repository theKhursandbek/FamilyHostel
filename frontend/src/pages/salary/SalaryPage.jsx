import { useState, useEffect, useCallback } from "react";
import { getSalaries } from "../../services/salaryService";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const BADGE_MAP = {
  paid: "badge-success",
  pending: "badge-warning",
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
      <span className={`badge ${BADGE_MAP[val] || "badge-muted"}`} style={{ textTransform: "capitalize" }}>
        {val || "—"}
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

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchSalaries} />;

  return (
    <div>
      <div className="page-header">
        <h1>Salary Records</h1>
      </div>

      <Table
        columns={columns}
        data={salaries}
        emptyMessage="No salary records found"
      />
    </div>
  );
}

export default SalaryPage;
