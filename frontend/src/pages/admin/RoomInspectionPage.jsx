import { useState, useEffect, useCallback } from "react";
import { getRoomInspections, createRoomInspection, getRooms } from "../../services/adminService";
import Button from "../../components/Button";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const BADGE_MAP = {
  clean: "badge-success",
  damaged: "badge-danger",
  needs_cleaning: "badge-warning",
};

const columns = [
  { key: "room_number", label: "Room" },
  {
    key: "status",
    label: "Status",
    render: (val) => (
      <span className={`badge ${BADGE_MAP[val] || "badge-muted"}`}>
        {val === "needs_cleaning" ? "Needs Cleaning" : val?.charAt(0).toUpperCase() + val?.slice(1)}
      </span>
    ),
  },
  { key: "notes", label: "Notes", render: (val) => val || "—" },
  { key: "inspector_name", label: "Inspector" },
  {
    key: "inspected_at",
    label: "Date",
    render: (val) => (val ? new Date(val).toLocaleString() : "—"),
  },
];

function RoomInspectionPage() {
  const [inspections, setInspections] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ room: "", status: "clean", notes: "" });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [inspData, roomData] = await Promise.all([
        getRoomInspections(),
        getRooms({ is_active: true }),
      ]);
      setInspections(inspData.results ?? inspData);
      setRooms(roomData.results ?? roomData);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.room) {
      alert("Please select a room");
      return;
    }
    setCreating(true);
    try {
      await createRoomInspection({
        room: Number(form.room),
        status: form.status,
        notes: form.notes,
      });
      setModalOpen(false);
      setForm({ room: "", status: "clean", notes: "" });
      fetchData();
    } catch (err) {
      const detail = err.response?.data;
      alert(typeof detail === "string" ? detail : detail?.detail || "Failed to create inspection");
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchData} />;

  return (
    <div>
      <div className="page-header">
        <h1>Room Inspections</h1>
        <Button onClick={() => setModalOpen(true)}>+ New Inspection</Button>
      </div>

      <Table columns={columns} data={inspections} emptyMessage="No inspections yet" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="New Room Inspection">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="label">
              Room <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <select
              className="select"
              value={form.room}
              onChange={(e) => setForm((p) => ({ ...p, room: e.target.value }))}
            >
              <option value="">Select room</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.room_number} — {r.room_type_name || "Room"}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="label">
              Status <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <select
              className="select"
              value={form.status}
              onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
            >
              <option value="clean">Clean</option>
              <option value="damaged">Damaged</option>
              <option value="needs_cleaning">Needs Cleaning</option>
            </select>
          </div>

          <div className="form-group">
            <label className="label">Notes</label>
            <textarea
              className="textarea"
              value={form.notes}
              onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
              placeholder="Optional notes..."
              rows={3}
            />
          </div>

          <div className="form-actions">
            <Button type="submit" disabled={creating}>{creating ? "Saving..." : "Save Inspection"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default RoomInspectionPage;
