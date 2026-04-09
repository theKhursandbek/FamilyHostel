import { useState, useEffect, useCallback } from "react";
import { getReports, exportCSV, getBranches } from "../../services/reportService";
import { useToast } from "../../context/ToastContext";
import StatCard from "../../components/StatCard";
import Table from "../../components/Table";
import Button from "../../components/Button";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const performanceColumns = [
  { key: "staff_name", label: "Staff" },
  {
    key: "tasks_completed",
    label: "Tasks Completed",
    render: (val) => val ?? 0,
  },
  {
    key: "avg_rating",
    label: "Avg Rating",
    render: (val) => (val !== null && val !== undefined ? Number(val).toFixed(1) : "—"),
  },
];

const attendanceColumns = [
  { key: "staff_name", label: "Staff" },
  { key: "days_present", label: "Present", render: (val) => val ?? 0 },
  { key: "days_absent", label: "Absent", render: (val) => val ?? 0 },
  { key: "days_off", label: "Days Off", render: (val) => val ?? 0 },
];

function ReportsPage() {
  const toast = useToast();
  const [report, setReport] = useState(null);
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  // Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [branch, setBranch] = useState("");

  const buildParams = useCallback(() => {
    const params = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (branch) params.branch = branch;
    return params;
  }, [dateFrom, dateTo, branch]);

  const fetchReport = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getReports(buildParams());
      setReport(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  const fetchBranches = useCallback(async () => {
    try {
      const data = await getBranches();
      const list = data.results ?? data;
      setBranches(list);
    } catch {
      setBranches([]);
      toast.warning("Could not load branches");
    }
  }, [toast]);

  useEffect(() => {
    fetchBranches();
  }, [fetchBranches]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const handleExport = async () => {
    try {
      setExporting(true);
      const response = await exportCSV(buildParams());
      const blob = new Blob([response.data], { type: "text/csv" });
      const url = globalThis.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `report_${dateFrom || "all"}_${dateTo || "all"}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      globalThis.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to export CSV");
    } finally {
      setExporting(false);
    }
  };

  const revenue = report?.total_revenue ?? report?.revenue ?? 0;
  const totalBookings = report?.total_bookings ?? report?.booking_count ?? 0;
  const completedTasks = report?.completed_tasks ?? 0;
  const activeStaff = report?.active_staff ?? 0;
  const staffPerformance = report?.staff_performance ?? [];
  const attendance = report?.attendance ?? [];

  return (
    <div>
      <div className="page-header">
        <h1>📊 Reports</h1>
        <Button
          variant="secondary"
          disabled={exporting || loading}
          onClick={handleExport}
        >
          {exporting ? "Exporting..." : "📥 Download CSV"}
        </Button>
      </div>

      {/* Filters */}
      <div className="card" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <label className="label" htmlFor="filter-from">From</label>
          <input
            id="filter-from"
            type="date"
            className="input"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="filter-to">To</label>
          <input
            id="filter-to"
            type="date"
            className="input"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="filter-branch">Branch</label>
          <select
            id="filter-branch"
            className="select"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
          >
            <option value="">All Branches</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name || `Branch #${b.id}`}
              </option>
            ))}
          </select>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => { setDateFrom(""); setDateTo(""); setBranch(""); }}
        >
          Clear filters
        </Button>
      </div>

      {error && (
        <div style={{ marginBottom: 16 }}>
          <ErrorMessage message={error} onRetry={fetchReport} />
        </div>
      )}

      {loading ? (
        <Loader />
      ) : (
        <>
          {/* Summary cards */}
          <div className="stat-grid">
            <StatCard
              title="Total Revenue"
              value={`${Number(revenue).toLocaleString()} сум`}
            />
            <StatCard
              title="Total Bookings"
              value={totalBookings}
            />
            <StatCard
              title="Tasks Completed"
              value={completedTasks}
            />
            <StatCard
              title="Active Staff"
              value={activeStaff}
            />
          </div>

          {/* Staff Performance */}
          <div className="section">
            <h3 className="section-title">
              👷 Staff Performance
            </h3>
            <Table
              columns={performanceColumns}
              data={staffPerformance}
              emptyMessage="No staff performance data"
            />
          </div>

          {/* Attendance Summary */}
          <div className="section">
            <h3 className="section-title">
              📋 Attendance Summary
            </h3>
            <Table
              columns={attendanceColumns}
              data={attendance}
              emptyMessage="No attendance data"
            />
          </div>
        </>
      )}
    </div>
  );
}

export default ReportsPage;
