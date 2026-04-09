import { useState, useEffect, useCallback } from "react";
import { getDayOffRequests, createDayOffRequest } from "../../services/staffService";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const BADGE_MAP = {
  pending: "badge-warning",
  approved: "badge-success",
  rejected: "badge-danger",
};

const columns = [
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
  { key: "reviewer_comment", label: "Comment", render: (val) => val || "—" },
];

function DaysOffPage() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ start_date: "", end_date: "", reason: "" });
  const [formErrors, setFormErrors] = useState({});

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDayOffRequests();
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

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setFormErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errors = {};
    if (!form.start_date) errors.start_date = "Required";
    if (!form.end_date) errors.end_date = "Required";
    if (form.start_date && form.end_date && form.end_date < form.start_date) {
      errors.end_date = "End date must be after start date";
    }
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setCreating(true);
    try {
      await createDayOffRequest(form);
      setModalOpen(false);
      setForm({ start_date: "", end_date: "", reason: "" });
      fetchRequests();
    } catch (err) {
      const detail = err.response?.data;
      alert(typeof detail === "string" ? detail : detail?.detail || detail?.non_field_errors?.[0] || "Failed to create request");
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchRequests} />;

  return (
    <div>
      <div className="page-header">
        <h1>Days Off Requests</h1>
        <Button onClick={() => setModalOpen(true)}>+ New Request</Button>
      </div>

      <Table columns={columns} data={requests} emptyMessage="No day-off requests" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Request Day Off">
        <form onSubmit={handleSubmit}>
          <Input label="Start Date" type="date" value={form.start_date} onChange={handleChange("start_date")} required error={formErrors.start_date} />
          <Input label="End Date" type="date" value={form.end_date} onChange={handleChange("end_date")} required error={formErrors.end_date} />
          <Input label="Reason (optional)" value={form.reason} onChange={handleChange("reason")} placeholder="Why do you need time off?" />
          <div className="form-actions">
            <Button type="submit" disabled={creating}>{creating ? "Submitting..." : "Submit Request"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default DaysOffPage;
