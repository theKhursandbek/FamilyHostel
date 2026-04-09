import { useState, useEffect, useCallback } from "react";
import { getTasks, assignTask } from "../../services/cleaningService";
import { getAccounts } from "../../services/directorService";
import Button from "../../components/Button";
import Table from "../../components/Table";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const BADGE_MAP = {
  pending: "badge-warning",
  in_progress: "badge-info",
  completed: "badge-success",
  retry_required: "badge-danger",
};
const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  retry_required: "Retry",
};

function TaskAssignmentPage() {
  const [tasks, setTasks] = useState([]);
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  // Assign modal
  const [assignModal, setAssignModal] = useState(false);
  const [assignTarget, setAssignTarget] = useState(null);
  const [selectedStaff, setSelectedStaff] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [taskData, accountData] = await Promise.all([
        getTasks(),
        getAccounts(),
      ]);
      setTasks(taskData.results ?? taskData);
      const accounts = accountData.results ?? accountData;
      setStaffList(accounts.filter((a) => a.roles?.includes("staff")));
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openAssignModal = (task) => {
    setAssignTarget(task);
    setSelectedStaff("");
    setAssignModal(true);
  };

  const handleAssign = async (e) => {
    e.preventDefault();
    if (!selectedStaff) return alert("Select a staff member");
    setActionLoading(assignTarget.id);
    try {
      await assignTask(assignTarget.id, Number(selectedStaff));
      setAssignModal(false);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to assign");
    } finally {
      setActionLoading(null);
    }
  };

  const columns = [
    { key: "room_number", label: "Room" },
    {
      key: "status",
      label: "Status",
      render: (val) => (
        <span className={`badge ${BADGE_MAP[val] || "badge-muted"}`}>
          {STATUS_LABELS[val] || val}
        </span>
      ),
    },
    { key: "assigned_to_name", label: "Assigned To", render: (val) => val || "Unassigned" },
    { key: "priority", label: "Priority", render: (val) => val?.charAt(0).toUpperCase() + val?.slice(1) },
    {
      key: "_actions",
      label: "",
      render: (_, row) =>
        row.status !== "completed" ? (
          <Button
            variant="secondary"
            size="sm"
            disabled={actionLoading === row.id}
            onClick={(e) => { e.stopPropagation(); openAssignModal(row); }}
          >
            {row.assigned_to_name ? "Reassign" : "Assign"}
          </Button>
        ) : null,
    },
  ];

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchData} />;

  return (
    <div>
      <div className="page-header"><h1>Task Assignment</h1></div>
      <Table columns={columns} data={tasks} emptyMessage="No cleaning tasks" />

      <Modal isOpen={assignModal} onClose={() => setAssignModal(false)} title={`Assign — Room ${assignTarget?.room_number}`}>
        <form onSubmit={handleAssign}>
          <div className="form-group">
            <label className="label">Staff Member *</label>
            <select
              className="select"
              value={selectedStaff}
              onChange={(e) => setSelectedStaff(e.target.value)}
            >
              <option value="">Select staff</option>
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>{s.phone}{s.full_name ? ` — ${s.full_name}` : ""}</option>
              ))}
            </select>
          </div>
          <div className="form-actions">
            <Button type="submit">Assign</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default TaskAssignmentPage;
