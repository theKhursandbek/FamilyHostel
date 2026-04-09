import { useState, useEffect } from "react";
import PropTypes from "prop-types";
import { getRooms } from "../services/bookingService";
import { useToast } from "../context/ToastContext";
import Input from "./Input";
import Button from "./Button";

function BookingForm({ onSubmit, loading = false }) {
  const toast = useToast();
  const [rooms, setRooms] = useState([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [form, setForm] = useState({
    room: "",
    branch: "",
    check_in_date: "",
    check_out_date: "",
    price_at_booking: "",
    discount_amount: "0",
  });
  const [errors, setErrors] = useState({});

  // Fetch available rooms
  useEffect(() => {
    async function fetchRooms() {
      try {
        const data = await getRooms({ status: "available", is_active: true });
        const roomList = data.results ?? data;
        setRooms(roomList);
      } catch {
        setRooms([]);
        toast.error("Failed to load rooms");
      } finally {
        setRoomsLoading(false);
      }
    }
    fetchRooms();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const handleRoomChange = (e) => {
    const roomId = e.target.value;
    const selected = rooms.find((r) => String(r.id) === roomId);
    setForm((prev) => ({
      ...prev,
      room: roomId,
      branch: selected ? String(selected.branch) : "",
    }));
    setErrors((prev) => ({ ...prev, room: "" }));
  };

  const validate = () => {
    const newErrors = {};
    if (!form.room) newErrors.room = "Room is required";
    if (!form.check_in_date) newErrors.check_in_date = "Check-in date is required";
    if (!form.check_out_date) newErrors.check_out_date = "Check-out date is required";
    if (!form.price_at_booking || Number(form.price_at_booking) <= 0) {
      newErrors.price_at_booking = "Price must be greater than 0";
    }
    if (form.check_in_date && form.check_out_date && form.check_out_date <= form.check_in_date) {
      newErrors.check_out_date = "Check-out must be after check-in";
    }
    if (Number(form.discount_amount) < 0) {
      newErrors.discount_amount = "Discount cannot be negative";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({
      room: Number(form.room),
      branch: Number(form.branch),
      check_in_date: form.check_in_date,
      check_out_date: form.check_out_date,
      price_at_booking: form.price_at_booking,
      discount_amount: form.discount_amount || "0",
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Room select */}
      <div className="form-group">
        <label htmlFor="room" className="label">
          Room <span style={{ color: "var(--danger)" }}>*</span>
        </label>
        <select
          id="room"
          value={form.room}
          onChange={handleRoomChange}
          disabled={roomsLoading}
          className={`select${errors.room ? " error" : ""}`}
        >
          <option value="">
            {roomsLoading ? "Loading rooms..." : "Select a room"}
          </option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.room_number} — {room.room_type_name || "Room"}
              {room.branch_name ? ` (${room.branch_name})` : ""}
            </option>
          ))}
        </select>
        {errors.room && (
          <p className="form-error">{errors.room}</p>
        )}
      </div>

      <Input
        label="Check-in Date"
        id="check_in_date"
        type="date"
        value={form.check_in_date}
        onChange={handleChange("check_in_date")}
        required
        error={errors.check_in_date}
      />

      <Input
        label="Check-out Date"
        id="check_out_date"
        type="date"
        value={form.check_out_date}
        onChange={handleChange("check_out_date")}
        required
        error={errors.check_out_date}
      />

      <Input
        label="Price"
        id="price_at_booking"
        type="number"
        value={form.price_at_booking}
        onChange={handleChange("price_at_booking")}
        placeholder="e.g. 150000"
        required
        error={errors.price_at_booking}
        min="0"
        step="1000"
      />

      <Input
        label="Discount (optional)"
        id="discount_amount"
        type="number"
        value={form.discount_amount}
        onChange={handleChange("discount_amount")}
        placeholder="0"
        error={errors.discount_amount}
        min="0"
        max="50000"
        step="1000"
      />

      <div className="form-actions">
        <Button type="submit" disabled={loading}>
          {loading ? "Creating..." : "Create Booking"}
        </Button>
      </div>
    </form>
  );
}

BookingForm.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

export default BookingForm;
