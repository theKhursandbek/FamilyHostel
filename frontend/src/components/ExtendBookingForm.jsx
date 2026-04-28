import { useState, useMemo } from "react";
import PropTypes from "prop-types";
import Input from "./Input";
import Button from "./Button";

const fmtMoney = (n) =>
  n === null || n === undefined ? "—" : `${Number(n).toLocaleString()} UZS`;

const nightsBetween = (a, b) => {
  if (!a || !b) return 0;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / (1000 * 60 * 60 * 24)));
};

/**
 * Extend an existing booking by pushing the check-out date later.
 *
 * The additional charge is auto-derived from the booking's per-night rate
 * (price_at_booking ÷ current nights) × extra nights, so the admin only
 * picks the new date.
 */
function ExtendBookingForm({ booking, onSubmit, loading = false }) {
  const minDate = booking?.check_out_date || "";
  const [newDate, setNewDate] = useState("");
  const [error, setError] = useState("");

  const currentNights = useMemo(
    () => nightsBetween(booking.check_in_date, booking.check_out_date),
    [booking.check_in_date, booking.check_out_date],
  );

  // Per-night rate with robust fallbacks (matches the card logic):
  //   1. room.base_price (live source of truth)
  //   2. price_at_booking ÷ current nights
  //   3. final_price ÷ current nights
  const perNight = useMemo(() => {
    const base = Number(booking.room_base_price || 0);
    if (base > 0) return base;
    const stored = Number(booking.price_at_booking || 0);
    if (stored > 0 && currentNights > 0) return Math.round(stored / currentNights);
    const finalP = Number(booking.final_price || 0);
    if (finalP > 0 && currentNights > 0) return Math.round(finalP / currentNights);
    return 0;
  }, [booking.room_base_price, booking.price_at_booking, booking.final_price, currentNights]);
  const missingRate = perNight <= 0;

  const extraNights = useMemo(
    () => (newDate ? nightsBetween(minDate, newDate) : 0),
    [newDate, minDate],
  );

  const additionalPrice = perNight * extraNights;
  const storedFinal = Number(booking.final_price || 0);
  const storedPrice = Number(booking.price_at_booking || 0);
  const discount = Number(booking.discount_amount || 0);
  let currentFinal = 0;
  if (storedFinal > 0) currentFinal = storedFinal;
  else if (storedPrice > 0) currentFinal = Math.max(0, storedPrice - discount);
  else currentFinal = Math.max(0, perNight * currentNights - discount);
  const newFinal = currentFinal + additionalPrice;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!newDate) {
      setError("New check-out date is required");
      return;
    }
    if (newDate <= minDate) {
      setError(`Must be after ${minDate}`);
      return;
    }
    if (missingRate) {
      setError("Cannot determine per-night rate for this booking.");
      return;
    }
    setError("");
    onSubmit({
      new_check_out_date: newDate,
      additional_price: String(additionalPrice || 0),
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div
        style={{
          marginBottom: 16,
          padding: "10px 14px",
          background: "var(--brand-cream, #fdfbf6)",
          border: "1px solid rgba(31,42,68,0.12)",
          borderRadius: 8,
          fontSize: 13,
          color: "var(--brand-navy, #1f2a44)",
          display: "grid",
          gap: 2,
        }}
      >
        <div><strong>Booking #{booking.id}</strong> — {booking.client_name}</div>
        <div>Room {booking.room_number}</div>
        <div>Current check-out: <strong>{minDate}</strong></div>
        <div>
          Per-night rate: <strong>{fmtMoney(perNight)}</strong>
          {currentNights > 0 && (
            <span style={{ color: "var(--text-muted, #6b7280)" }}>
              {" "}· current stay: {currentNights} night{currentNights === 1 ? "" : "s"} = {fmtMoney(currentFinal)}
            </span>
          )}
        </div>
      </div>

      <Input
        label="New Check-out Date"
        id="new_check_out_date"
        type="date"
        value={newDate}
        onChange={(e) => { setNewDate(e.target.value); setError(""); }}
        min={minDate}
        required
        error={error}
      />

      {extraNights > 0 && (
        <div
          style={{
            marginTop: 4,
            marginBottom: 16,
            padding: "12px 14px",
            background: "rgba(176,141,87,0.08)",
            border: "1px solid rgba(176,141,87,0.3)",
            borderRadius: 8,
            fontSize: 13,
            color: "var(--brand-navy, #1f2a44)",
            display: "grid",
            gap: 4,
          }}
        >
          <div>
            +{extraNights} extra night{extraNights === 1 ? "" : "s"} × {fmtMoney(perNight)} ={" "}
            <strong>{fmtMoney(additionalPrice)}</strong>
          </div>
          <div style={{ color: "var(--text-muted, #6b7280)" }}>
            New total:{" "}
            <strong style={{ color: "var(--brand-accent, #b08d57)" }}>
              {fmtMoney(newFinal)}
            </strong>
          </div>
        </div>
      )}

      <div className="form-actions">
        <Button type="submit" disabled={loading || !newDate || extraNights <= 0}>
          {loading ? "Extending…" : "Extend Booking"}
        </Button>
      </div>
    </form>
  );
}

ExtendBookingForm.propTypes = {
  booking: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    client_name: PropTypes.string,
    room_number: PropTypes.string,
    check_in_date: PropTypes.string.isRequired,
    check_out_date: PropTypes.string.isRequired,
    price_at_booking: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    discount_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    room_base_price: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    final_price: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  }).isRequired,
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

export default ExtendBookingForm;
