import { useState, useEffect, useCallback } from "react";
import { getTasks, assignTask } from "../../services/cleaningService";
import { getAccounts } from "../../services/directorService";
import Button from "../../components/Button";
import Table from "../../components/Table";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const STATUS_COLORS = {
  pending: "#f59e0b",
  in_progress: "#3b82f6",
  completed: "#22c55e",
  retry_required: "#ef4444",
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
        <span
          style={{
            padding: "2px 10px",
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
            color: "#fff",
            backgroundColor: STATUS_COLORS[val] || "#6b7280",
          }}
        >
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
      <h1 style={{ marginBottom: 20 }}>Task Assignment</h1>
      <Table columns={columns} data={tasks} emptyMessage="No cleaning tasks" />

      <Modal isOpen={assignModal} onClose={() => setAssignModal(false)} title={`Assign — Room ${assignTarget?.room_number}`}>
        <form onSubmit={handleAssign}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Staff Member *</label>
            <select
              value={selectedStaff}
              onChange={(e) => setSelectedStaff(e.target.value)}
              style={{ width: "100%", padding: 8, border: "1px solid #dadce0", borderRadius: 4, fontSize: 14, boxSizing: "border-box" }}
            >
              <option value="">Select staff</option>
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>{s.phone}{s.full_name ? ` — ${s.full_name}` : ""}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button type="submit">Assign</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default TaskAssignmentPage;
