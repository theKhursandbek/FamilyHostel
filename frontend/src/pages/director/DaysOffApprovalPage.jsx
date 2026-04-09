import { useState, useEffect, useCallback } from "react";
import { getAllDayOffRequests, approveDayOff, rejectDayOff } from "../../services/directorService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const BADGE_MAP = {
  pending: "badge-warning",
  approved: "badge-success",
  rejected: "badge-danger",
};

function DaysOffApprovalPage() {
  const toast = useToast();
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
      toast.success(`Request ${action === "approve" ? "approved" : "rejected"}`);
      fetchRequests();
    } catch (err) {
      toast.error(err.response?.data?.detail || `Failed to ${action}`);
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
        <span className={`badge ${BADGE_MAP[val] || "badge-muted"}`} style={{ textTransform: "capitalize" }}>
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
      <div className="page-header"><h1>Days Off Approvals</h1></div>
      <Table columns={columns} data={requests} emptyMessage="No day-off requests" />
    </div>
  );
}

export default DaysOffApprovalPage;
