import { useState, useEffect, useCallback, useMemo } from "react";
import { fmtMoney, rawMoney } from "../utils/moneyInput";
import PropTypes from "prop-types";
import { ChevronLeft, ChevronRight, Maximize2 } from "lucide-react";
import { getRooms, getAvailability, getBookings } from "../services/bookingService";
import { useToast } from "../context/ToastContext";
import {
  validateName,
  formatNameInput,
  validatePhone,
  formatPhoneInput,
  validatePassport,
  formatPassportInput,
  validateDOB,
  maxDOBForAge,
  todayLocalISO,
  addDaysISO,
} from "../utils/guestValidation";
import Input from "./Input";
import Button from "./Button";
import Loader from "./Loader";
import Lightbox from "./Lightbox";
import PaymentMethodSelect from "./PaymentMethodSelect";

/**
 * 3-step hold-first booking wizard.
 *
 *   1. Choose Room     (all branch rooms; booked ones grayed out + show their
 *                       checkout date — no pre-booking from the admin website)
 *   2. Guest Details   (name, phone, passport, DOB — strict real-time masks)
 *   3. Dates & Hold    (check-in inherits today; pick checkout only; live
 *                       price; choose a payment method) → submit
 */

const STEPS = [
  { key: "room",     title: "Choose Room" },
  { key: "guest",    title: "Guest Details" },
  { key: "combined", title: "Dates & Hold" },
];

const fmt = (n) => Number(n || 0).toLocaleString() + " сум";

/** ISO (YYYY-MM-DD) → DD.MM.YYYY for the booked-room checkout label. */
function fmtDMY(iso) {
  if (!iso) return "";
  const [y, m, d] = String(iso).split("-");
  if (!y || !m || !d) return String(iso);
  return `${d}.${m}.${y}`;
}

function diffNights(a, b) {
  if (!a || !b) return 0;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / (1000 * 60 * 60 * 24)));
}

// ── Validation helpers (ported 1:1 from the Telegram Mini App) ───────────
const todayISO = todayLocalISO;

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

function RoomCard({ room, isActive, disabled, freeFrom, onSelect, onZoom }) {
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

  // Booked / unavailable rooms: grayed out, non-selectable. They display ONLY
  // the checkout date (plain text, no tags) so the operator sees when the room
  // frees up. This also covers upcoming Telegram pre-bookings (look-ahead).
  if (disabled) {
    return (
      <div className="room-pick-card room-pick-card--booked" aria-disabled="true">
        <div className="room-pick-card__media">
          {total > 0 ? (
            <img src={images[0]} alt={`Room ${room.room_number}`} />
          ) : (
            <div className="room-pick-card__placeholder">🏠</div>
          )}
          <span className="room-pick-card__veil" />
        </div>
        <div className="room-pick-card__body">
          <div className="room-pick-card__title">
            <span className="room-pick-card__num">№ {room.room_number}</span>
            <span className="badge badge-accent badge-sm">
              {room.room_type_name || "Room"}
            </span>
          </div>
          {freeFrom && (
            <div className="room-pick-card__freefrom">{fmtDMY(freeFrom)}</div>
          )}
        </div>
      </div>
    );
  }

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
  disabled: PropTypes.bool,
  freeFrom: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  onZoom: PropTypes.func.isRequired,
};

function RoomGrid({ rooms, selectedId, states, onSelect, onZoom }) {
  if (!rooms.length) {
    return (
      <div className="empty-state">
        <p>No rooms in this branch.</p>
      </div>
    );
  }
  return (
    <div className="room-pick-grid">
      {rooms.map((room) => {
        const st = states[room.id] || {};
        return (
          <RoomCard
            key={room.id}
            room={room}
            isActive={String(room.id) === String(selectedId)}
            disabled={Boolean(st.disabled)}
            freeFrom={st.freeFrom || null}
            onSelect={onSelect}
            onZoom={onZoom}
          />
        );
      })}
    </div>
  );
}
RoomGrid.propTypes = {
  rooms: PropTypes.array.isRequired,
  selectedId: PropTypes.any,
  states: PropTypes.object.isRequired,
  onSelect: PropTypes.func.isRequired,
  onZoom: PropTypes.func.isRequired,
};

// ── Main wizard ─────────────────────────────────────────────────────────

/**
 * Per-room availability for Step 1. A room is disabled when it has an active
 * (paid) booking whose checkout is still in the future — current occupancy OR
 * an upcoming Telegram pre-booking (look-ahead) — or it is mid-cleaning.
 * Booked rooms also surface the checkout date (so the operator sees when they
 * free up).
 */
function deriveRoomStates(roomList, bookingList, today) {
  const byRoom = {};
  for (const b of Array.isArray(bookingList) ? bookingList : []) {
    if (b.status !== "paid") continue; // only active bookings hold a room
    if (!b.check_out_date || b.check_out_date < today) continue;
    const prev = byRoom[b.room];
    if (!prev || b.check_in_date < prev.check_in_date) byRoom[b.room] = b;
  }
  const states = {};
  for (const r of Array.isArray(roomList) ? roomList : []) {
    const booked = byRoom[r.id];
    const statusBlocked = r.status === "cleaning" || r.status === "maintenance";
    states[r.id] = {
      disabled: Boolean(booked) || statusBlocked || r.is_active === false,
      freeFrom: booked ? booked.check_out_date : null,
    };
  }
  return states;
}

function BookingWizard({ onSubmit, loading = false, branchId = null }) {
  const toast = useToast();
  const today = todayISO();
  const [step, setStep] = useState(0);
  const [rooms, setRooms] = useState([]);
  const [roomStates, setRoomStates] = useState({}); // id → { disabled, freeFrom }
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [room, setRoom] = useState(null);
  const [checkOut, setCheckOut] = useState("");
  const [discount, setDiscount] = useState("0");
  const [method, setMethod] = useState("cash");
  const [guest, setGuest] = useState({ first_name: "", last_name: "", phone: "", passport_number: "", date_of_birth: "" });
  const [zoom, setZoom] = useState(null);
  const [nextStart, setNextStart] = useState(null); // selected room's next booking → checkout cap

  // ── Load all branch rooms + their active bookings, then derive availability.
  //    Booked rooms (now OR an upcoming Telegram pre-booking) are grayed out;
  //    the admin website never pre-books, so we only need "free today" rooms.
  const fetchRooms = useCallback(async () => {
    setRoomsLoading(true);
    setLoadError(false);
    try {
      const roomParams = { is_active: true, page_size: 1000 };
      if (branchId) roomParams.branch = branchId;
      const bookingParams = { status: "paid", page_size: 1000 };
      if (branchId) bookingParams.branch = branchId;

      const [roomData, bookingData] = await Promise.all([
        getRooms(roomParams),
        getBookings(bookingParams).catch(() => ({ results: [] })),
      ]);
      const roomList = roomData.results ?? roomData;
      const bookingList = bookingData.results ?? bookingData;
      const list = Array.isArray(roomList) ? roomList : [];
      setRooms(list);
      setRoomStates(deriveRoomStates(list, bookingList, today));
    } catch {
      setRooms([]);
      setRoomStates({});
      setLoadError(true);
      toast.error("Failed to load rooms");
    } finally {
      setRoomsLoading(false);
    }
  }, [toast, branchId, today]);

  useEffect(() => { fetchRooms(); }, [fetchRooms]);

  // ── When a room is picked, look ahead for its next booking to cap checkout.
  useEffect(() => {
    if (!room?.id) { setNextStart(null); return undefined; }
    let alive = true;
    getAvailability(room.id, { after: today })
      .then((data) => { if (alive) setNextStart(data.next_booking_start || null); })
      .catch(() => { if (alive) setNextStart(null); });
    return () => { alive = false; };
  }, [room?.id, today]);

  // ── Live price (check-in is always "today").
  const nights = useMemo(() => diffNights(today, checkOut), [today, checkOut]);
  const subtotal = useMemo(
    () => (room ? Number(room.base_price) * nights : 0),
    [room, nights],
  );
  const discountValue = Math.max(0, Number(rawMoney(discount)) || 0);
  const total = Math.max(0, subtotal - discountValue);

  const updateGuest = (field, value) => setGuest((g) => ({ ...g, [field]: value }));

  // ── Guest validity drives the disabled state (no red error messages — the
  //    masks block bad keystrokes outright and the button gates progress).
  const guestValid = useMemo(() => (
    validateName(guest.first_name).ok
    && validateName(guest.last_name).ok
    && validatePhone(guest.phone).ok
    && validatePassport(guest.passport_number).ok
    && validateDOB(guest.date_of_birth, { minAge: 16 }).ok
  ), [guest]);

  // ── Checkout validity for the combined step.
  const checkoutValid = Boolean(checkOut)
    && checkOut > today
    && nights > 0
    && (!nextStart || checkOut <= nextStart)
    && discountValue < (subtotal || Infinity);

  const maxCheckout = nextStart || undefined;

  const next = () => {
    if (step === 0 && !room) { toast.error("Please choose a room first."); return; }
    if (step === 1 && !guestValid) { toast.error("Please complete the guest details."); return; }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };
  const back = () => setStep((s) => Math.max(0, s - 1));

  const selectRoom = (r) => {
    setRoom(r);
    setCheckOut(""); // reset the checkout whenever the room changes
  };

  const submit = (ev) => {
    ev.preventDefault();
    if (!guestValid) { toast.error("Please complete the guest details."); return; }
    if (!checkoutValid) { toast.error("Please pick a valid checkout date."); return; }
    onSubmit({
      full_name: `${validateName(guest.first_name).value} ${validateName(guest.last_name).value}`.trim(),
      phone: validatePhone(guest.phone).value,
      passport_number: validatePassport(guest.passport_number).value,
      date_of_birth: guest.date_of_birth,
      room: Number(room.id),
      room_number: room.room_number,
      branch: Number(room.branch),
      check_in_date: today,
      check_out_date: checkOut,
      price_at_booking: String(subtotal || 0),
      discount_amount: String(discountValue || 0),
      method,
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
          <span>Could not load rooms.</span>
          <Button type="button" variant="secondary" onClick={fetchRooms}>Retry</Button>
        </div>
      );
    } else {
      body = (
        <RoomGrid
          rooms={rooms}
          selectedId={room?.id}
          states={roomStates}
          onSelect={selectRoom}
          onZoom={(r, startIndex) => setZoom({ room: r, startIndex })}
        />
      );
    }
  } else if (step === 1) {
    body = (
      <div className="wizard-pane">
        <Input
          label="First Name"
          id="first_name"
          value={guest.first_name}
          onChange={(e) => updateGuest("first_name", formatNameInput(e.target.value))}
          placeholder="e.g. Botir"
          autoComplete="off"
          required
        />
        <Input
          label="Last Name"
          id="last_name"
          value={guest.last_name}
          onChange={(e) => updateGuest("last_name", formatNameInput(e.target.value))}
          placeholder="e.g. Aliyev"
          autoComplete="off"
          required
        />
        <Input
          label="Phone"
          id="phone"
          type="tel"
          inputMode="tel"
          value={guest.phone}
          onChange={(e) => updateGuest("phone", formatPhoneInput(e.target.value))}
          onFocus={() => { if (!guest.phone) updateGuest("phone", "+998"); }}
          placeholder="+998 90 123 45 67"
          autoComplete="off"
          required
        />
        <Input
          label="Passport Number"
          id="passport_number"
          value={guest.passport_number}
          onChange={(e) => updateGuest("passport_number", formatPassportInput(e.target.value))}
          placeholder="e.g. AB1234567"
          maxLength={9}
          autoComplete="off"
          required
        />
        <Input
          label="Date of Birth"
          id="date_of_birth"
          type="date"
          max={maxDOBForAge(16)}
          value={guest.date_of_birth}
          onChange={(e) => updateGuest("date_of_birth", e.target.value)}
          required
        />
      </div>
    );
  } else {
    body = (
      <form onSubmit={submit} className="wizard-pane">
        <div className="wizard-room-summary">
          <div>
            <div className="wizard-room-summary__title">
              № {room.room_number} — {room.room_type_name || "Room"}
            </div>
            <div className="wizard-room-summary__sub">
              Check-in: <strong>{fmtDMY(today)}</strong> (today)
            </div>
          </div>
          <div className="wizard-room-summary__right">
            <div className="wizard-room-summary__price">
              {fmt(room.base_price)} <span>/ night</span>
            </div>
          </div>
        </div>

        <Input
          label="Check-out Date"
          id="check_out_date"
          type="date"
          min={addDaysISO(today, 1)}
          max={maxCheckout}
          value={checkOut}
          onChange={(e) => setCheckOut(e.target.value)}
          required
        />
        {nextStart && (
          <p className="wizard-hint">
            Available up to <strong>{fmtDMY(nextStart)}</strong> (next guest&apos;s check-in).
          </p>
        )}

        <PaymentMethodSelect value={method} onChange={setMethod} />

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
              type="text"
              inputMode="numeric"
              className="input cost-summary__input"
              value={fmtMoney(discount)}
              onChange={(e) => setDiscount(fmtMoney(e.target.value))}
              placeholder="0"
            />
          </div>
          <div className="cost-summary__divider" />
          <div className="cost-summary__row cost-summary__total">
            <span>Total</span>
            <span>{fmt(total)}</span>
          </div>
        </div>

        <div className="form-actions wizard-actions">
          <Button type="button" variant="secondary" onClick={back}>← Back</Button>
          <Button type="submit" disabled={loading || !checkoutValid}>
            {loading ? "Creating…" : "Create Hold"}
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
              <Button type="button" variant="secondary" onClick={back}>← Back</Button>
            )}
            <Button
              type="button"
              onClick={next}
              disabled={(step === 0 && !room) || (step === 1 && !guestValid)}
            >
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
