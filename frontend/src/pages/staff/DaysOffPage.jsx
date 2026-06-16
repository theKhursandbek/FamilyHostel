import { useState, useEffect, useCallback } from "react";
import { CalendarDays } from "lucide-react";
import { getDayOffRequests, createDayOffRequest } from "../../services/staffService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const STATUS_TONE = {
  pending: "staff-badge--warning",
  approved: "staff-badge--success",
  rejected: "staff-badge--danger",
};

function fmtDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function DaysOffPage() {
  const toast = useToast();
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
      toast.success("Day-off request submitted");
      fetchRequests();
    } catch (err) {
      const detail = err.response?.data;
      toast.error(typeof detail === "string" ? detail : detail?.detail || detail?.non_field_errors?.[0] || "Failed to create request");
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchRequests} />;

  return (
    <div className="staff-page">
      <header className="staff-hero staff-hero--split">
        <div>
          <h1 className="staff-hero__title">Days Off</h1>
          <p className="staff-hero__sub">Request and track your time off</p>
        </div>
        <Button size="sm" onClick={() => setModalOpen(true)}>+ New</Button>
      </header>

      {requests.length === 0 ? (
        <div className="staff-empty">
          <span className="staff-empty__icon" aria-hidden>
            <CalendarDays size={26} strokeWidth={1.6} />
          </span>
          <p className="staff-empty__title">No requests yet</p>
          <p className="staff-empty__sub">Tap “+ New” to request a day off.</p>
        </div>
      ) : (
        <ul className="staff-stack">
          {requests.map((r) => (
            <li key={r.id} className="staff-rec">
              <div className="staff-rec__top">
                <span className="staff-rec__title">
                  {fmtDate(r.start_date)} → {fmtDate(r.end_date)}
                </span>
                <span className={`staff-badge ${STATUS_TONE[r.status] || ""}`}>
                  {r.status}
                </span>
              </div>
              {r.reason && <p className="staff-rec__meta">{r.reason}</p>}
              {r.reviewer_comment && (
                <p className="staff-rec__meta">
                  <strong>Reviewer:</strong> {r.reviewer_comment}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

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
