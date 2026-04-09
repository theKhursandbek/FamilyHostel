import { useState, useEffect, useCallback } from "react";
import { getAllDayOffRequests, approveDayOff, rejectDayOff } from "../../services/directorService";
import Button from "../../components/Button";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const STATUS_COLORS = {
  pending: "#f59e0b",
  approved: "#22c55e",
  rejected: "#ef4444",
};

function DaysOffApprovalPage() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAllDayOffRequests();
      setRequests(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleAction = async (id, action) => {
    setActionLoading(id);
    try {
      if (action === "approve") {
        await approveDayOff(id);
      } else {
        await rejectDayOff(id);
      }
      fetchRequests();
    } catch (err) {
      alert(err.response?.data?.detail || `Failed to ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  const columns = [
    { key: "requester_name", label: "Staff", render: (val) => val || "—" },
    { key: "start_date", label: "Start" },
    { key: "end_date", label: "End" },
    { key: "reason", label: "Reason", render: (val) => val || "—" },
    {
      key: "status",
      label: "Status",
      render: (val) => (
        <span
          style={{
            padding: "2px 10px",
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
            color: "#fff",
            backgroundColor: STATUS_COLORS[val] || "#6b7280",
            textTransform: "capitalize",
          }}
        >
          {val}
        </span>
      ),
    },
    {
      key: "_actions",
      label: "",
      render: (_, row) =>
        row.status === "pending" ? (
          <div style={{ display: "flex", gap: 6 }}>
            <Button
              size="sm"
              disabled={actionLoading === row.id}
              onClick={(e) => { e.stopPropagation(); handleAction(row.id, "approve"); }}
            >
              {actionLoading === row.id ? "…" : "Approve"}
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={actionLoading === row.id}
              onClick={(e) => { e.stopPropagation(); handleAction(row.id, "reject"); }}
            >
              {actionLoading === row.id ? "…" : "Reject"}
            </Button>
          </div>
        ) : null,
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchRequests} />;

  return (
    <div>
      <h1 style={{ marginBottom: 20 }}>Days Off Approvals</h1>
      <Table columns={columns} data={requests} emptyMessage="No day-off requests" />
    </div>
  );
}

export default DaysOffApprovalPage;
