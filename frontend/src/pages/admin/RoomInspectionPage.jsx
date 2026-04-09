import { useState, useEffect, useCallback } from "react";
import { getRoomInspections, createRoomInspection, getRooms } from "../../services/adminService";
import Button from "../../components/Button";
import Modal from "../../components/Modal";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const STATUS_COLORS = {
  clean: "#22c55e",
  damaged: "#ef4444",
  needs_cleaning: "#f59e0b",
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>Room Inspections</h1>
        <Button onClick={() => setModalOpen(true)}>+ New Inspection</Button>
      </div>

      <Table columns={columns} data={inspections} emptyMessage="No inspections yet" />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="New Room Inspection">
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
              Room <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <select
              value={form.room}
              onChange={(e) => setForm((p) => ({ ...p, room: e.target.value }))}
              style={{ width: "100%", padding: 8, border: "1px solid #dadce0", borderRadius: 4, fontSize: 14, boxSizing: "border-box" }}
            >
              <option value="">Select room</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.room_number} — {r.room_type_name || "Room"}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
              Status <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <select
              value={form.status}
              onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
              style={{ width: "100%", padding: 8, border: "1px solid #dadce0", borderRadius: 4, fontSize: 14, boxSizing: "border-box" }}
            >
              <option value="clean">Clean</option>
              <option value="damaged">Damaged</option>
              <option value="needs_cleaning">Needs Cleaning</option>
            </select>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Notes</label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
              placeholder="Optional notes..."
              rows={3}
              style={{ width: "100%", padding: 8, border: "1px solid #dadce0", borderRadius: 4, fontSize: 14, boxSizing: "border-box", resize: "vertical" }}
            />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button type="submit" disabled={creating}>{creating ? "Saving..." : "Save Inspection"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default RoomInspectionPage;
