import { useState, useEffect, useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import { ChevronLeft, ChevronRight, Maximize2 } from "lucide-react";
import { getRooms } from "../services/bookingService";
import { useToast } from "../context/ToastContext";
import Input from "./Input";
import Button from "./Button";
import Loader from "./Loader";
import Lightbox from "./Lightbox";

/**
 * 4-step walk-in booking wizard.
 *
 *   1. Pick a Room   (visual cards with photo + price)
 *   2. Pick Dates    (check-in / check-out)
 *   3. Cost Summary  (auto total, optional discount)
 *   4. Guest Details (name, phone, passport) → submit
 */

const STEPS = [
  { key: "room",  title: "Choose Room" },
  { key: "dates", title: "Select Dates" },
  { key: "cost",  title: "Confirm Price" },
  { key: "guest", title: "Guest Details" },
];

const fmt = (n) => Number(n || 0).toLocaleString() + " сум";

function diffNights(a, b) {
  if (!a || !b) return 0;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / (1000 * 60 * 60 * 24)));
}

// ── Reusable progress bar ───────────────────────────────────────────────
function StepBar({ step }) {
  return (
    <div className="wizard-steps">
      {STEPS.map((s, i) => {
        let state = "todo";
        if (i < step) state = "done";
        else if (i === step) state = "active";
        return (
          <div key={s.key} className={`wizard-step wizard-step--${state}`}>
            <div className="wizard-step__dot">{i < step ? "✓" : i + 1}</div>
            <div className="wizard-step__label">{s.title}</div>
            {i < STEPS.length - 1 && <div className="wizard-step__bar" />}
          </div>
        );
      })}
    </div>
  );
}
StepBar.propTypes = { step: PropTypes.number.isRequired };

// ── Step 1: Room cards ──────────────────────────────────────────────────
function roomImageUrls(room) {
  const list = (room.images || [])
    .map((img) => img?.image || img?.image_url)
    .filter(Boolean);
  if (list.length === 0 && room.primary_image_url) list.push(room.primary_image_url);
  return list;
}

function RoomCard({ room, isActive, onSelect, onZoom }) {
  const images = roomImageUrls(room);
  const total = images.length;
  const [idx, setIdx] = useState(0);

  const prev = (e) => {
    e.stopPropagation();
    setIdx((i) => (i - 1 + total) % total);
  };
  const next = (e) => {
    e.stopPropagation();
    setIdx((i) => (i + 1) % total);
  };

  return (
    <button
      type="button"
      onClick={() => onSelect(room)}
      className={`room-pick-card ${isActive ? "is-active" : ""}`}
    >
      <div className="room-pick-card__media">
        {total > 0 ? (
          <>
            <img src={images[idx]} alt={`Room ${room.room_number}`} />

            {total > 1 && (
              <>
                <button
                  type="button"
                  className="room-pick-card__nav room-pick-card__nav--prev"
                  onClick={prev}
                  aria-label="Previous photo"
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  type="button"
                  className="room-pick-card__nav room-pick-card__nav--next"
                  onClick={next}
                  aria-label="Next photo"
                >
                  <ChevronRight size={16} />
                </button>
                <div className="room-pick-card__dots">
                  {images.map((url, i) => (
                    <span
                      key={url}
                      className={`room-pick-card__dot ${i === idx ? "is-active" : ""}`}
                    />
                  ))}
                </div>
              </>
            )}

            <button
              type="button"
              className="room-pick-card__zoom"
              onClick={(e) => {
                e.stopPropagation();
                onZoom(room, idx);
              }}
              aria-label="View full screen"
              title="View full screen"
            >
              <Maximize2 size={14} />
            </button>

            <span className="room-pick-card__count">
              {total} photo{total === 1 ? "" : "s"}
            </span>
          </>
        ) : (
          <div className="room-pick-card__placeholder">🏠</div>
        )}

        {isActive && <span className="room-pick-card__check">✓</span>}
      </div>

      <div className="room-pick-card__body">
        <div className="room-pick-card__title">
          <span className="room-pick-card__num">№ {room.room_number}</span>
          <span className="badge badge-accent badge-sm">
            {room.room_type_name || "Room"}
          </span>
        </div>

        {room.branch_name && (
          <div className="room-pick-card__sub">{room.branch_name}</div>
        )}

        <div className="room-pick-card__price">
          <span>{fmt(room.base_price)}</span>
          <span className="room-pick-card__per">/ night</span>
        </div>
      </div>
    </button>
  );
}
RoomCard.propTypes = {
  room: PropTypes.object.isRequired,
  isActive: PropTypes.bool,
  onSelect: PropTypes.func.isRequired,
  onZoom: PropTypes.func.isRequired,
};

function RoomGrid({ rooms, selectedId, onSelect, onZoom }) {
  if (!rooms.length) {
    return (
      <div className="empty-state">
        <p>No available rooms right now.</p>
      </div>
    );
  }
  return (
    <div className="room-pick-grid">
      {rooms.map((room) => (
        <RoomCard
          key={room.id}
          room={room}
          isActive={String(room.id) === String(selectedId)}
          onSelect={onSelect}
          onZoom={onZoom}
        />
      ))}
    </div>
  );
}
RoomGrid.propTypes = {
  rooms: PropTypes.array.isRequired,
  selectedId: PropTypes.any,
  onSelect: PropTypes.func.isRequired,
  onZoom: PropTypes.func.isRequired,
};

// ── Main wizard ─────────────────────────────────────────────────────────
function BookingWizard({ onSubmit, loading = false, branchId = null }) {
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [rooms, setRooms] = useState([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [room, setRoom] = useState(null);
  const [dates, setDates] = useState({ check_in_date: "", check_out_date: "" });
  const [discount, setDiscount] = useState("0");
  const [guest, setGuest] = useState({ full_name: "", phone: "", passport_number: "" });
  const [errors, setErrors] = useState({});
  const [zoom, setZoom] = useState(null);

  // ── Load available rooms once
  const fetchRooms = useCallback(async () => {
    setRoomsLoading(true);
    setLoadError(false);
    try {
      const params = { status: "available", is_active: true };
      if (branchId) params.branch = branchId;
      const data = await getRooms(params);
      const list = data.results ?? data;
      setRooms(Array.isArray(list) ? list : []);
    } catch {
      setRooms([]);
      setLoadError(true);
      toast.error("Failed to load rooms");
    } finally {
      setRoomsLoading(false);
    }
  }, [toast, branchId]);

  useEffect(() => { fetchRooms(); }, [fetchRooms]);

  // ── Computed totals
  const nights = useMemo(
    () => diffNights(dates.check_in_date, dates.check_out_date),
    [dates],
  );
  const subtotal = useMemo(
    () => (room ? Number(room.base_price) * nights : 0),
    [room, nights],
  );
  const discountValue = Math.max(0, Number(discount) || 0);
  const total = Math.max(0, subtotal - discountValue);

  // ── Per-step validation
  const canAdvance = () => {
    if (step === 0) return Boolean(room);
    if (step === 1) {
      return (
        Boolean(dates.check_in_date) &&
        Boolean(dates.check_out_date) &&
        nights > 0
      );
    }
    if (step === 2) return discountValue < subtotal && total > 0;
    return true;
  };

  const next = () => {
    if (!canAdvance()) {
      if (step === 1) {
        setErrors({ dates: "Check-out must be after check-in." });
      }
      return;
    }
    setErrors({});
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };
  const back = () => {
    setErrors({});
    setStep((s) => Math.max(0, s - 1));
  };

  const validateGuest = () => {
    const e = {};
    if (!guest.full_name.trim()) e.full_name = "Full name is required";
    if (!guest.phone.trim()) e.phone = "Phone is required";
    if (!guest.passport_number.trim()) e.passport_number = "Passport is required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = (e) => {
    e.preventDefault();
    if (!validateGuest()) return;
    onSubmit({
      full_name: guest.full_name.trim(),
      phone: guest.phone.trim(),
      passport_number: guest.passport_number.trim(),
      room: Number(room.id),
      branch: Number(room.branch),
      check_in_date: dates.check_in_date,
      check_out_date: dates.check_out_date,
      price_at_booking: String(subtotal || 0),
      discount_amount: String(discountValue || 0),
    });
  };

  // ── Render step body
  let body;
  if (step === 0) {
    if (roomsLoading) {
      body = <Loader />;
    } else if (loadError) {
      body = (
        <div className="alert alert-error" style={{ display: "flex", justifyContent: "space-between" }}>
          <span>Could not load available rooms.</span>
          <Button type="button" variant="ghost" onClick={fetchRooms}>Retry</Button>
        </div>
      );
    } else {
      body = (
        <RoomGrid
          rooms={rooms}
          selectedId={room?.id}
          onSelect={(r) => setRoom(r)}
          onZoom={(r, startIndex) => setZoom({ room: r, startIndex })}
        />
      );
    }
  } else if (step === 1) {
    body = (
      <div className="wizard-pane">
        <div className="wizard-room-summary">
          <div>
            <div className="wizard-room-summary__title">
              № {room.room_number} — {room.room_type_name || "Room"}
            </div>
            {room.branch_name && (
              <div className="wizard-room-summary__sub">{room.branch_name}</div>
            )}
          </div>
          <div className="wizard-room-summary__right">
            <div className="wizard-room-summary__price">
              {fmt(room.base_price)} <span>/ night</span>
            </div>
            {roomImageUrls(room).length > 0 && (
              <button
                type="button"
                className="wizard-room-summary__photos"
                onClick={() => setZoom({ room, startIndex: 0 })}
              >
                View photos ({roomImageUrls(room).length})
              </button>
            )}
          </div>
        </div>
        <div className="form-row">
          <Input
            label="Check-in Date"
            id="check_in_date"
            type="date"
            value={dates.check_in_date}
            onChange={(e) => setDates((d) => ({ ...d, check_in_date: e.target.value }))}
            required
          />
          <Input
            label="Check-out Date"
            id="check_out_date"
            type="date"
            value={dates.check_out_date}
            onChange={(e) => setDates((d) => ({ ...d, check_out_date: e.target.value }))}
            required
            error={errors.dates}
          />
        </div>
        {nights > 0 && (
          <p className="wizard-hint">
            Stay length: <strong>{nights}</strong> night{nights === 1 ? "" : "s"}
          </p>
        )}
      </div>
    );
  } else if (step === 2) {
    body = (
      <div className="wizard-pane">
        <div className="cost-summary">
          <div className="cost-summary__row">
            <span>Room № {room.room_number}</span>
            <span>{fmt(room.base_price)} × {nights}</span>
          </div>
          <div className="cost-summary__row">
            <span>Subtotal</span>
            <span>{fmt(subtotal)}</span>
          </div>
          <div className="cost-summary__row cost-summary__row--input">
            <label htmlFor="discount">Discount</label>
            <input
              id="discount"
              type="number"
              className="input cost-summary__input"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
              min="0"
              step="1000"
              placeholder="0"
            />
          </div>
          <div className="cost-summary__divider" />
          <div className="cost-summary__row cost-summary__total">
            <span>Total</span>
            <span>{fmt(total)}</span>
          </div>
        </div>
        {discountValue >= subtotal && subtotal > 0 && (
          <p className="form-error">Discount cannot be greater than or equal to subtotal.</p>
        )}
      </div>
    );
  } else {
    body = (
      <form onSubmit={submit} className="wizard-pane">
        <Input
          label="Full Name"
          id="full_name"
          value={guest.full_name}
          onChange={(e) => setGuest((g) => ({ ...g, full_name: e.target.value }))}
          placeholder="e.g. Aliyev Botir"
          required
          error={errors.full_name}
        />
        <Input
          label="Phone"
          id="phone"
          type="tel"
          value={guest.phone}
          onChange={(e) => setGuest((g) => ({ ...g, phone: e.target.value }))}
          placeholder="+998 90 123 45 67"
          required
          error={errors.phone}
        />
        <Input
          label="Passport Number"
          id="passport_number"
          value={guest.passport_number}
          onChange={(e) => setGuest((g) => ({ ...g, passport_number: e.target.value }))}
          placeholder="e.g. AA1234567"
          required
          error={errors.passport_number}
        />
        <div className="cost-summary cost-summary--compact">
          <div className="cost-summary__row cost-summary__total">
            <span>Total to charge</span>
            <span>{fmt(total)}</span>
          </div>
        </div>
        <div className="form-actions wizard-actions">
          <Button type="button" variant="ghost" onClick={back}>← Back</Button>
          <Button type="submit" disabled={loading}>
            {loading ? "Creating…" : "Confirm Booking"}
          </Button>
        </div>
      </form>
    );
  }

  return (
    <>
      <div className="wizard">
        <StepBar step={step} />
        <div className="wizard-body">{body}</div>
        {step < STEPS.length - 1 && (
          <div className="form-actions wizard-actions">
            {step > 0 && (
              <Button type="button" variant="ghost" onClick={back}>← Back</Button>
            )}
            <Button type="button" onClick={next} disabled={!canAdvance()}>
              Next →
            </Button>
          </div>
        )}
      </div>

      {zoom && (
        <Lightbox
          images={roomImageUrls(zoom.room)}
          startIndex={zoom.startIndex}
          onClose={() => setZoom(null)}
          caption={`Room № ${zoom.room.room_number} — ${zoom.room.room_type_name || "Room"}`}
        />
      )}
    </>
  );
}

BookingWizard.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  branchId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

export default BookingWizard;
