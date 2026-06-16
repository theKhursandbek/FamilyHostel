import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import {
  getBookings,
  getBooking,
  createBookingHold,
  checkoutBooking,
  extendBooking,
} from "../services/bookingService";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import { useBranchScope } from "../context/BranchScopeContext";
import usePersistedBranch from "../hooks/usePersistedBranch";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import BookingWizard from "../components/BookingWizard";
import ExtendBookingForm from "../components/ExtendBookingForm";
import Button from "../components/Button";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

const STATUS_LABELS = {
  paid:      "Paid",
  completed: "Checked out",
  canceled:  "Canceled",
};

const FILTERS = [
  { key: "active", label: "Active" },
  { key: "past", label: "Past" },
];

const fmtMoney = (n) =>
  n === null || n === undefined ? "—" : `${Number(n).toLocaleString()} UZS`;

const fmtDate = (s) => {
  if (!s) return "—";
  try {
    const d = new Date(s);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return s;
  }
};

const nightsBetween = (a, b) => {
  if (!a || !b) return 0;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / (1000 * 60 * 60 * 24)));
};

// True when checkout happens before the scheduled check-out date (no refund).
const isEarlyCheckout = (booking) => {
  if (!booking?.check_out_date) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const co = new Date(booking.check_out_date);
  co.setHours(0, 0, 0, 0);
  return today < co;
};

function BookingCard({ booking, onOpen, onExtend, onComplete, busy }) {
  const n = nightsBetween(booking.check_in_date, booking.check_out_date);
  const discount = Number(booking.discount_amount || 0);
  const baseRate = Number(booking.room_base_price || 0);
  const storedFinal = Number(booking.final_price || 0);
  const storedPrice = Number(booking.price_at_booking || 0);

  // Total = backend's authoritative final_price.
  // Fallbacks (in order) keep things sane if final_price is missing:
  //   - price_at_booking − discount  (price_at_booking IS the full stay total)
  //   - room_base_price × nights − discount  (re-derive from current rate)
  let total = 0;
  if (storedFinal > 0) total = storedFinal;
  else if (storedPrice > 0) total = Math.max(0, storedPrice - discount);
  else if (baseRate > 0 && n > 0) total = Math.max(0, baseRate * n - discount);

  // Backend-authoritative balance fields (fall back to client-side math).
  const paid = Number(booking.paid_total ?? 0);
  const balance = booking.balance_due == null
    ? Math.max(0, total - paid)
    : Number(booking.balance_due);

  const status = booking.status || "paid";
  const handleCardClick = () => onOpen(booking);
  const stop = (e) => e.stopPropagation();

  return (
    <div className={`bk-card is-${status}`}>
      <button
        type="button"
        className="bk-card__open-area"
        onClick={handleCardClick}
      >
        {/* Head: room chip · guest + id · status */}
        <div className="bk-card__head">
          <span className="bk-card__room">{String(booking.room_number ?? "—")}</span>
          <div className="bk-card__head-main">
            <h3 className="bk-card__guest" title={booking.client_name || "Guest"}>
              {booking.client_name || "Guest"}
            </h3>
            <span className="bk-card__sub">
              #{booking.branch_number ?? booking.id}
              {booking.source === "telegram" && (
                <span className="bk-card__tg" title="Booked online via Telegram">✈ Telegram</span>
              )}
            </span>
          </div>
          <span className={`bk-card__status is-${status}`}>
            {STATUS_LABELS[status] || status}
          </span>
        </div>

        {/* Stay strip */}
        <div className="bk-card__stay">
          <div className="bk-card__leg">
            <span className="bk-card__leg-lbl">Check-in</span>
            <span className="bk-card__leg-val">{fmtDate(booking.check_in_date)}</span>
          </div>
          <span className="bk-card__nights">{n} night{n === 1 ? "" : "s"}</span>
          <div className="bk-card__leg bk-card__leg--end">
            <span className="bk-card__leg-lbl">Check-out</span>
            <span className="bk-card__leg-val">{fmtDate(booking.check_out_date)}</span>
          </div>
        </div>

        {/* Footer: money */}
        <div className="bk-card__foot">
          <div className="bk-card__money">
            <span className="bk-card__total">{fmtMoney(total)}</span>
            {balance > 0 ? (
              <span className="bk-card__balance">Balance due {fmtMoney(balance)}</span>
            ) : (
              paid > 0 && <span className="bk-card__paid">Paid in full</span>
            )}
          </div>
        </div>
      </button>

      <div
        className="bk-card__actions"
        onClick={stop}
        onKeyDown={stop}
        role="toolbar"
        aria-label="Booking actions"
      >
        {status === "paid" && (
          <Button variant="secondary" size="sm" onClick={() => onExtend(booking)}>
            Extend
          </Button>
        )}
        {status === "paid" && (
          <Button
            variant="primary"
            size="sm"
            disabled={busy.complete === booking.id}
            onClick={() => onComplete(booking)}
          >
            {busy.complete === booking.id ? "…" : "Complete"}
          </Button>
        )}
      </div>
    </div>
  );
}

BookingCard.propTypes = {
  booking: PropTypes.object.isRequired,
  onOpen: PropTypes.func.isRequired,
  onExtend: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  busy: PropTypes.object.isRequired,
};

function BookingsPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuth();
  const isSuperAdmin = user?.roles?.includes("superadmin") ?? false;
  const [branchId, setBranchId] = usePersistedBranch(
    "branchScope:bookings",
    isSuperAdmin,
    user?.branch_id ?? null,
  );

  // Register branch scope in header
  const { register, unregister } = useBranchScope();
  useEffect(() => { register(branchId, setBranchId); }, [branchId, register, setBranchId]);
  useEffect(() => () => unregister(), [unregister]);

  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [pendingHold, setPendingHold] = useState(null);
  const [completingId, setCompletingId] = useState(null);
  const [completeTarget, setCompleteTarget] = useState(null); // booking pending checkout
  const [extendTarget, setExtendTarget] = useState(null);
  const [extending, setExtending] = useState(false);
  const [filter, setFilter] = useState("active");
  const [search, setSearch] = useState("");

  const fetchBookings = useCallback(async () => {
    // CEO must pick a branch first; until then show the empty state.
    if (isSuperAdmin && !branchId) {
      setBookings([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (branchId) params.branch = branchId;
      const data = await getBookings(params);
      setBookings(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load bookings");
    } finally {
      setLoading(false);
    }
  }, [branchId, isSuperAdmin]);

  useEffect(() => { fetchBookings(); }, [fetchBookings]);

  const handleCreate = async (formData) => {
    setCreating(true);
    try {
      const draft = await createBookingHold(formData);
      setPendingHold({
        draftId: draft.draft_id,
        roomNumber: formData.room_number,
        guestName: formData.full_name,
        expiresAt: draft.expires_at,
      });
      setIsModalOpen(false);
      toast.success("Room held for 5 minutes");
    } catch (err) {
      const detail = err.response?.data;
      let msg = "Failed to create booking";
      if (typeof detail === "string") msg = detail;
      else if (detail) {
        msg =
          detail.error?.message ||
          detail.detail ||
          detail.non_field_errors?.[0] ||
          detail.passport_number?.[0] ||
          detail.phone?.[0] ||
          detail.full_name?.[0] ||
          detail.room?.[0] ||
          msg;
      }
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleExtend = async (payload) => {
    if (!extendTarget) return;
    setExtending(true);
    try {
      await extendBooking(extendTarget.id, payload);
      toast.success("Booking extended");
      setExtendTarget(null);
      fetchBookings();
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.error?.message ||
            detail?.detail ||
            detail?.new_check_out_date?.[0] ||
            detail?.additional_price?.[0] ||
            detail?.non_field_errors?.[0] ||
            "Failed to extend booking";
      toast.error(msg);
    } finally {
      setExtending(false);
    }
  };

  const handleComplete = (booking) => {
    if (booking.status !== "paid") return;
    setCompleteTarget(booking);
  };

  const confirmComplete = async () => {
    const booking = completeTarget;
    if (!booking) return;
    setCompletingId(booking.id);
    try {
      await checkoutBooking(booking.id);
      toast.success("Guest checked out");
      setCompleteTarget(null);
      fetchBookings();
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.error?.message ||
            detail?.detail ||
            "Failed to check out";
      toast.error(msg);
    } finally {
      setCompletingId(null);
    }
  };

  const filtered = useMemo(() => {
    const raw = search.trim().toLowerCase();
    // A leading "#" searches by Booking ID only; anything else is a standard
    // text / phone search that never matches the id.
    const isIdSearch = raw.startsWith("#");
    const q = isIdSearch ? raw.slice(1).trim() : raw;
    return bookings.filter((b) => {
      if (filter === "active" && b.status !== "paid") return false;
      if (filter === "past" && !(b.status === "completed" || b.status === "canceled")) return false;
      if (!q) return true;
      if (isIdSearch) {
        const id = String(b.branch_number ?? b.id).toLowerCase();
        return id === q || id.includes(q);
      }
      return (
        String(b.room_number || "").toLowerCase().includes(q) ||
        String(b.client_name || "").toLowerCase().includes(q) ||
        String(b.client_phone || "").toLowerCase().includes(q)
      );
    });
  }, [bookings, filter, search]);

  const counts = useMemo(() => {
    const c = { all: bookings.length, active: 0, past: 0 };
    for (const b of bookings) {
      if (b.status === "paid") c.active++;
      else if (b.status === "completed" || b.status === "canceled") c.past++;
    }
    return c;
  }, [bookings]);

  const ceoMustPick = isSuperAdmin && !branchId;

  const pendingHoldLabel = pendingHold?.expiresAt
    ? new Date(pendingHold.expiresAt).toLocaleString()
    : "";

  let completeMsg = "";
  if (completeTarget) {
    completeMsg = isEarlyCheckout(completeTarget)
      ? `Early checkout for room ${completeTarget.room_number}. The unused nights will NOT be refunded.`
      : `Check out room ${completeTarget.room_number}?`;
  }
  const completeTone = completeTarget && isEarlyCheckout(completeTarget) ? "danger" : "primary";

  return (
    <div>
      <div className="page-header">
        <h1>Bookings</h1>
      </div>

      {error && !ceoMustPick && (
        <ErrorMessage message={error} onRetry={fetchBookings} />
      )}
      {loading && !ceoMustPick && !error && <Loader />}

      {ceoMustPick && (
        <div className="branch-empty">
          <p className="branch-empty__title">Select a branch to begin</p>
          <p className="branch-empty__hint">
            As CEO you oversee every branch. Pick one above to view and manage its bookings.
          </p>
        </div>
      )}

      {!ceoMustPick && !loading && !error && (
        <>
          {pendingHold && (
            <div className="alert alert-info" style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div>
                <strong>Room hold active.</strong>{" "}
                {pendingHold.roomNumber ? `Room № ${pendingHold.roomNumber}` : "Selected room"}
                {pendingHold.guestName ? ` for ${pendingHold.guestName}` : ""}
                {pendingHoldLabel ? ` until ${pendingHoldLabel}` : ""}.
              </div>
              <Button type="button" variant="secondary" size="sm" onClick={() => setPendingHold(null)}>
                Dismiss
              </Button>
            </div>
          )}
          <div className="bookings-toolbar">
        <div className="bookings-filter">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`bookings-filter__chip ${filter === f.key ? "is-active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              <span className="bookings-filter__count">{counts[f.key] || 0}</span>
            </button>
          ))}
        </div>
        <div className="bookings-search-row">
          <input
            type="search"
            className="input bookings-search"
            placeholder="Search #id · room · guest · phone"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button onClick={() => setIsModalOpen(true)}>New Booking</Button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <p>No bookings match your filters.</p>
        </div>
      ) : (
        <div className="bookings-grid">
          {filtered.map((b) => (
            <BookingCard
              key={b.id}
              booking={b}
              onOpen={(row) => navigate(`/bookings/${row.id}`)}
              onExtend={async (b) => {
                try {
                  const fresh = await getBooking(b.id);
                  setExtendTarget({ ...b, ...fresh });
                } catch {
                  setExtendTarget(b);
                }
              }}
              onComplete={handleComplete}
              busy={{ complete: completingId }}
            />
          ))}
        </div>
      )}
        </>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="New Booking"
        size="wide"
      >
        <BookingWizard onSubmit={handleCreate} loading={creating} branchId={branchId} />
      </Modal>

      <Modal
        isOpen={Boolean(extendTarget)}
        onClose={() => setExtendTarget(null)}
        title="Extend Booking"
      >
        {extendTarget && (
          <ExtendBookingForm
            booking={extendTarget}
            onSubmit={handleExtend}
            loading={extending}
          />
        )}
      </Modal>

      {/* Checkout confirmation (warns on early checkout — no refund) */}
      <ConfirmDialog
        isOpen={Boolean(completeTarget)}
        onClose={() => setCompleteTarget(null)}
        onConfirm={confirmComplete}
        title="Check out guest?"
        tone={completeTone}
        confirmLabel="Check out"
        loading={Boolean(completingId)}
        message={completeMsg}
      />
    </div>
  );
}

export default BookingsPage;
