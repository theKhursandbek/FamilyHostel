import { useState, useEffect, useCallback } from "react";
import { getReports, exportCSV, getBranches } from "../../services/reportService";
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
    }
  }, []);

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
      setError(err.response?.data?.detail || "Failed to export CSV");
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>📊 Reports</h2>
        <Button
          variant="secondary"
          disabled={exporting || loading}
          onClick={handleExport}
        >
          {exporting ? "Exporting..." : "📥 Download CSV"}
        </Button>
      </div>

      {/* Filters */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "flex-end",
          marginBottom: 24,
          padding: 16,
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
        }}
      >
        <div>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
            From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{
              padding: 6,
              border: "1px solid #dadce0",
              borderRadius: 4,
              fontSize: 13,
            }}
          />
        </div>
        <div>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
            To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            style={{
              padding: 6,
              border: "1px solid #dadce0",
              borderRadius: 4,
              fontSize: 13,
            }}
          />
        </div>
        <div>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
            Branch
          </label>
          <select
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            style={{
              padding: 6,
              border: "1px solid #dadce0",
              borderRadius: 4,
              fontSize: 13,
            }}
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
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 28 }}>
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
          <div style={{ marginBottom: 28 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>
              👷 Staff Performance
            </h3>
            <Table
              columns={performanceColumns}
              data={staffPerformance}
              emptyMessage="No staff performance data"
            />
          </div>

          {/* Attendance Summary */}
          <div>
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>
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
