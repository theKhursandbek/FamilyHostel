import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { getRooms } from "../services/bookingService";
import { useToast } from "../context/ToastContext";
import Input from "./Input";
import Button from "./Button";
import Select from "./Select";

/**
 * Walk-in booking form.
 *
 * Every booking made through the admin panel is for a brand-new guest who
 * walks in off the street.  We capture identity (name, phone, passport) plus
 * the room and dates, then submit one atomic walk-in payload to
 * POST /bookings/bookings/walk-in/.
 */
function BookingForm({ onSubmit, loading = false }) {
  const toast = useToast();
  const [rooms, setRooms] = useState([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    phone: "",
    passport_number: "",
    room: "",
    branch: "",
    check_in_date: "",
    check_out_date: "",
    discount_amount: "0",
  });
  const [errors, setErrors] = useState({});

  const fetchRooms = useCallback(async () => {
    setRoomsLoading(true);
    setLoadError(false);
    try {
      const data = await getRooms({ status: "available", is_active: true });
      const roomList = data.results ?? data;
      setRooms(Array.isArray(roomList) ? roomList : []);
    } catch {
      setRooms([]);
      setLoadError(true);
      toast.error("Failed to load rooms");
    } finally {
      setRoomsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  const roomOptions = rooms.map((room) => {
    const branchSuffix = room.branch_name ? ` (${room.branch_name})` : "";
    return {
      value: room.id,
      label: `${room.room_number} \u2014 ${room.room_type_name || "Room"}${branchSuffix}`,
    };
  });

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const handleRoomChange = (roomId) => {
    const selected = rooms.find((r) => String(r.id) === String(roomId));
    setForm((prev) => ({
      ...prev,
      room: roomId,
      branch: selected ? String(selected.branch) : "",
    }));
    setErrors((prev) => ({ ...prev, room: "" }));
  };

  const validate = () => {
    const newErrors = {};
    if (!form.full_name.trim()) newErrors.full_name = "Full name is required";
    if (!form.phone.trim()) newErrors.phone = "Phone is required";
    if (!form.passport_number.trim()) newErrors.passport_number = "Passport number is required";
    if (!form.room) newErrors.room = "Room is required";
    if (!form.check_in_date) newErrors.check_in_date = "Check-in date is required";
    if (!form.check_out_date) newErrors.check_out_date = "Check-out date is required";
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
      full_name: form.full_name.trim(),
      phone: form.phone.trim(),
      passport_number: form.passport_number.trim(),
      room: Number(form.room),
      branch: Number(form.branch),
      check_in_date: form.check_in_date,
      check_out_date: form.check_out_date,
      discount_amount: form.discount_amount || "0",
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      {loadError && (
        <div
          className="alert alert-error"
          style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
        >
          <span>Could not load available rooms.</span>
          <Button type="button" variant="ghost" onClick={fetchRooms} disabled={roomsLoading}>
            Retry
          </Button>
        </div>
      )}

      {/* --- Guest section --- */}
      <div
        style={{
          marginBottom: 16,
          padding: "12px 14px",
          background: "var(--brand-cream, #fdfbf6)",
          border: "1px solid rgba(31,42,68,0.12)",
          borderRadius: 8,
        }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: 0.6,
            textTransform: "uppercase",
            color: "var(--brand-navy, #1f2a44)",
            marginBottom: 8,
          }}
        >
          Guest details
        </div>

        <Input
          label="Full Name"
          id="full_name"
          value={form.full_name}
          onChange={handleChange("full_name")}
          placeholder="e.g. Aliyev Botir"
          required
          error={errors.full_name}
        />
        <Input
          label="Phone"
          id="phone"
          type="tel"
          value={form.phone}
          onChange={handleChange("phone")}
          placeholder="+998 90 123 45 67"
          required
          error={errors.phone}
        />
        <Input
          label="Passport Number"
          id="passport_number"
          value={form.passport_number}
          onChange={handleChange("passport_number")}
          placeholder="e.g. AA1234567"
          required
          error={errors.passport_number}
        />
      </div>

      {/* --- Booking section --- */}
      <div className="form-group">
        <label htmlFor="room" className="label">
          Room <span style={{ color: "var(--brand-danger)" }}>*</span>
        </label>
        <Select
          id="room"
          value={form.room}
          onChange={handleRoomChange}
          options={roomOptions}
          loading={roomsLoading}
          disabled={loadError && !roomsLoading}
          placeholder={loadError ? "Unavailable \u2014 retry above" : "Select a room"}
          emptyText="No available rooms"
          error={Boolean(errors.room)}
        />
        {errors.room && <p className="form-error">{errors.room}</p>}
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

      {/* Room price (read-only — set when the room was created) */}
      {(() => {
        const selected = rooms.find((r) => String(r.id) === String(form.room));
        const price = selected?.base_price;
        return (
          <div
            style={{
              margin: "4px 0 16px",
              padding: "10px 14px",
              background: "var(--brand-cream, #fdfbf6)",
              border: "1px solid rgba(31,42,68,0.12)",
              borderRadius: 8,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              color: "var(--brand-navy, #1f2a44)",
              fontSize: 14,
            }}
          >
            <span style={{ fontWeight: 600 }}>Room price (per night)</span>
            <span style={{ fontWeight: 700 }}>
              {price
                ? `${Number(price).toLocaleString()} сум`
                : "— select a room —"}
            </span>
          </div>
        );
      })()}

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
