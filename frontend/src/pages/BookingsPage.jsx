import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import {
  getBookings,
  getBooking,
  createWalkInBooking,
  cancelBooking,
  checkoutBooking,
  extendBooking,
} from "../services/bookingService";
import { recordPayment } from "../services/paymentService";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import usePersistedBranch from "../hooks/usePersistedBranch";
import Modal from "../components/Modal";
import BookingWizard from "../components/BookingWizard";
import ExtendBookingForm from "../components/ExtendBookingForm";
import BranchSelector from "../components/BranchSelector";
import Button from "../components/Button";
import Loader from "../components/Loader";
import ErrorMessage from "../components/ErrorMessage";

const STATUS_LABELS = {
  pending:   "Pending",
  paid:      "Paid",
  completed: "Checked out",
  canceled:  "Canceled",
};

const BADGE_MAP = {
  pending:   "badge-warning",
  paid:      "badge-success",
  completed: "badge-muted",
  canceled:  "badge-danger",
};

const FILTERS = [
  { key: "all",       label: "All" },
  { key: "pending",   label: "Pending" },
  { key: "paid",      label: "Paid" },
  { key: "completed", label: "Checked out" },
  { key: "canceled",  label: "Canceled" },
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

function BookingCard({ booking, onOpen, onExtend, onCancel, onComplete, onMarkPaid, busy }) {
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

  // Per-night hint: prefer the room's current nightly rate, else derive.
  let perNight = 0;
  if (baseRate > 0) {
    perNight = baseRate;
  } else if (n > 0 && storedPrice > 0) {
    perNight = Math.round(storedPrice / n);
  }

  // Backend-authoritative balance fields (fall back to client-side math).
  const paid = Number(booking.paid_total ?? 0);
  const balance = booking.balance_due == null
    ? Math.max(0, total - paid)
    : Number(booking.balance_due);

  const handleCardClick = () => onOpen(booking);
  const handleCardKey = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpen(booking);
    }
  };
  const stop = (e) => e.stopPropagation();

  return (
    <div
      className={`booking-card booking-card--lux is-${booking.status || "pending"}`}
      role="button"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={handleCardKey}
    >
      <span className="booking-card__rail" aria-hidden />

      {/* Head: crest + ID on the left, status + name stacked on the right */}
      <div className="booking-card__head">
        <div className="booking-card__crest-wrap">
          <span className="booking-card__crest" aria-hidden>
            {String(booking.room_number ?? "·")}
          </span>          {/* eslint-disable-next-line no-irregular-whitespace */}          <span className="booking-card__bid" aria-label={`Booking ID ${booking.id}`}>
            № {booking.id}
          </span>
        </div>
        <div className="booking-card__head-body">
          <span className={`booking-card__status is-${booking.status || "pending"}`}>
            {STATUS_LABELS[booking.status] || booking.status}
          </span>
          {booking.source === "telegram" && (
            <span
              className="booking-card__source-badge"
              title="Booked via Telegram"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: "0.72rem",
                padding: "2px 8px",
                borderRadius: 999,
                background: "#e0f2fe",
                color: "#0369a1",
                fontWeight: 600,
                marginTop: 4,
              }}
            >
              ✈ Telegram
            </span>
          )}
          <h3 className="booking-card__title" title={booking.client_name || "Guest"}>
            {booking.client_name || "Guest"}
          </h3>
        </div>
      </div>

      {/* Date ledger */}
      <div className="booking-card__dates">
        <div>
          <div className="booking-card__dlabel">Check-in</div>
          <div className="booking-card__dval">{fmtDate(booking.check_in_date)}</div>
        </div>
        <div className="booking-card__arrow">—</div>
        <div>
          <div className="booking-card__dlabel">Check-out</div>
          <div className="booking-card__dval">{fmtDate(booking.check_out_date)}</div>
        </div>
        <div className="booking-card__nights">
          {n} night{n === 1 ? "" : "s"}
        </div>
      </div>

      {/* Foot: billing nameplate + actions */}
      <div className="booking-card__foot">
        <div className="booking-card__price">
          <span className="booking-card__plabel">Total due</span>
          <span className="booking-card__pval">{fmtMoney(total)}</span>
          {perNight > 0 && n > 0 && (
            <span className="booking-card__phint">
              {fmtMoney(perNight)} × {n} night{n === 1 ? "" : "s"}
              {discount > 0 ? ` − ${fmtMoney(discount)}` : ""}
            </span>
          )}
          {paid > 0 && balance > 0 && (
            <span className="booking-card__phint">
              Paid {fmtMoney(paid)} · Balance <strong>{fmtMoney(balance)}</strong>
            </span>
          )}
        </div>
        <div
          className="booking-card__actions"
          onClick={stop}
          onKeyDown={stop}
          role="toolbar"
          aria-label="Booking actions"
        >
          {(booking.status === "pending" || booking.status === "paid") && (
            <Button variant="ghost" size="sm" className="booking-card__btn" onClick={() => onExtend(booking)}>
              Extend
            </Button>
          )}
          {booking.status === "pending" && !(paid > 0 && balance <= 0) && (
            <Button
              variant="primary"
              size="sm"
              className="booking-card__btn"
              disabled={busy.pay === booking.id}
              onClick={() => onMarkPaid(booking, balance > 0 ? balance : total)}
            >
              {(() => {
                if (busy.pay === booking.id) return "…";
                return paid > 0 ? "Pay balance" : "Pay";
              })()}
            </Button>
          )}
          {booking.status === "pending" && (
            <Button
              variant="danger"
              size="sm"
              className="booking-card__btn"
              disabled={busy.cancel === booking.id}
              onClick={() => onCancel(booking)}
            >
              {busy.cancel === booking.id ? "…" : "Cancel"}
            </Button>
          )}
          {booking.status === "paid" && (
            <Button
              variant="secondary"
              size="sm"
              className="booking-card__btn"
              disabled={busy.complete === booking.id}
              onClick={() => onComplete(booking)}
            >
              {busy.complete === booking.id ? "…" : "Complete"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

BookingCard.propTypes = {
  booking: PropTypes.object.isRequired,
  onOpen: PropTypes.func.isRequired,
  onExtend: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  onMarkPaid: PropTypes.func.isRequired,
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
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [cancellingId, setCancellingId] = useState(null);
  const [completingId, setCompletingId] = useState(null);
  const [payingId, setPayingId] = useState(null);
  const [payTarget, setPayTarget] = useState(null); // { booking, amount } when pay modal is open
  const [payMethod, setPayMethod] = useState("cash");
  const [extendTarget, setExtendTarget] = useState(null);
  const [extending, setExtending] = useState(false);
  const [filter, setFilter] = useState("all");
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
      await createWalkInBooking(formData);
      setIsModalOpen(false);
      toast.success("Guest checked in & booking created");
      fetchBookings();
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

  const handleCancel = async (booking) => {
    if (booking.status !== "pending") return;
    if (!globalThis.confirm(`Cancel booking for room ${booking.room_number}?`)) return;
    setCancellingId(booking.id);
    try {
      await cancelBooking(booking.id);
      toast.success("Booking canceled");
      fetchBookings();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to cancel booking");
    } finally {
      setCancellingId(null);
    }
  };

  const handleComplete = async (booking) => {
    if (booking.status !== "paid") return;

    // Detect early checkout (today is before scheduled check-out date) so
    // the confirm message warns the user no refund will be issued.
    const todayDate = new Date();
    todayDate.setHours(0, 0, 0, 0);
    const checkout = new Date(booking.check_out_date);
    checkout.setHours(0, 0, 0, 0);
    const isEarly = todayDate < checkout;

    const message = isEarly
      ? `Early checkout for room ${booking.room_number}. ` +
        "The unused nights will NOT be refunded. Continue?"
      : `Check out room ${booking.room_number}?`;
    if (!globalThis.confirm(message)) return;

    setCompletingId(booking.id);
    try {
      await checkoutBooking(booking.id);
      toast.success("Guest checked out");
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

  const handleMarkPaid = (booking, total) => {
    if (booking.status !== "pending") return;
    const paidSoFar = Number(booking.paid_total ?? 0);
    const backendBalance = booking.balance_due == null
      ? null
      : Number(booking.balance_due);
    if (backendBalance === 0 && paidSoFar > 0) {
      toast.error("This booking is already fully paid — please refresh.");
      fetchBookings();
      return;
    }
    const amount = Number(total);
    if (!amount || amount <= 0) {
      toast.error("Cannot determine amount to pay");
      return;
    }
    // Open the payment modal — the user picks a method via a real Select.
    setPayMethod("cash");
    setPayTarget({ booking, amount });
  };

  const submitPayment = async () => {
    if (!payTarget) return;
    const { booking, amount } = payTarget;
    setPayingId(booking.id);
    try {
      await recordPayment({
        booking: booking.id,
        amount,
        payment_type: "manual",
        method: payMethod,
      });
      toast.success("Payment recorded");
      setPayTarget(null);
      fetchBookings();
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.error?.message ||
            detail?.detail ||
            detail?.amount?.[0] ||
            detail?.booking?.[0] ||
            detail?.method?.[0] ||
            detail?.non_field_errors?.[0] ||
            "Failed to record payment";
      toast.error(msg);
    } finally {
      setPayingId(null);
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return bookings.filter((b) => {
      if (filter !== "all" && b.status !== filter) return false;
      if (!q) return true;
      return (
        String(b.room_number || "").toLowerCase().includes(q) ||
        String(b.client_name || "").toLowerCase().includes(q) ||
        String(b.branch_name || "").toLowerCase().includes(q)
      );
    });
  }, [bookings, filter, search]);

  const counts = useMemo(() => {
    const c = { all: bookings.length };
    for (const b of bookings) c[b.status] = (c[b.status] || 0) + 1;
    return c;
  }, [bookings]);

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchBookings} />;

  const ceoMustPick = isSuperAdmin && !branchId;

  return (
    <div>
      <div className="page-header">
        <h1>Bookings</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <BranchSelector value={branchId} onChange={setBranchId} />
          {!ceoMustPick && (
            <Button onClick={() => setIsModalOpen(true)}>+ New Booking</Button>
          )}
        </div>
      </div>

      {ceoMustPick ? (
        <div className="branch-empty">
          <p className="branch-empty__title">Select a branch to begin</p>
          <p className="branch-empty__hint">
            As CEO you oversee every branch. Pick one above to view and manage its bookings.
          </p>
        </div>
      ) : (
        <>
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
        <input
          type="search"
          className="input bookings-search"
          placeholder="Search room, guest, branch…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
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
              onCancel={handleCancel}
              onComplete={handleComplete}
              onMarkPaid={handleMarkPaid}
              busy={{ cancel: cancellingId, complete: completingId, pay: payingId }}
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

      <Modal
        isOpen={Boolean(payTarget)}
        onClose={() => { if (!payingId) setPayTarget(null); }}
        title="Record Payment"
      >
        {payTarget && (
          <div>
            <div
              style={{
                marginBottom: 16,
                padding: "12px 14px",
                background: "var(--brand-cream, #fdfbf6)",
                border: "1px solid rgba(31,42,68,0.12)",
                borderRadius: 8,
              }}
            >
              <div style={{ fontSize: 13, color: "var(--brand-navy, #1f2a44)" }}>
                Room <strong>{payTarget.booking.room_number}</strong>
                {payTarget.booking.client_name ? ` — ${payTarget.booking.client_name}` : ""}
              </div>
              <div style={{ marginTop: 6, fontSize: 18, fontWeight: 700 }}>
                {Number(payTarget.amount).toLocaleString()} UZS
              </div>
            </div>

            <div className="form-group">
              <div
                className="label"
                style={{ marginBottom: 8 }}
                id="pay-method-label"
              >
                Payment method <span style={{ color: "var(--brand-danger)" }}>*</span>
              </div>
              <div
                role="radiogroup"
                aria-labelledby="pay-method-label"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: 8,
                }}
              >
                {[
                  { value: "cash", label: "Cash" },
                  { value: "terminal", label: "Terminal (POS)" },
                  { value: "qr", label: "QR code" },
                  { value: "card_transfer", label: "Card transfer" },
                ].map((opt) => {
                  const active = payMethod === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => setPayMethod(opt.value)}
                      style={{
                        padding: "12px 14px",
                        borderRadius: 10,
                        border: active
                          ? "2px solid var(--brand-primary, #1f2a44)"
                          : "1px solid rgba(31,42,68,0.18)",
                        background: active
                          ? "var(--accent-soft, #efe7d4)"
                          : "var(--bg-card, #fff)",
                        color: "var(--brand-navy, #1f2a44)",
                        fontWeight: active ? 700 : 500,
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "all 120ms ease",
                      }}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="form-actions" style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <Button
                type="button"
                variant="ghost"
                disabled={Boolean(payingId)}
                onClick={() => setPayTarget(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                disabled={Boolean(payingId)}
                onClick={submitPayment}
              >
                {payingId ? "Saving..." : "Confirm Payment"}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default BookingsPage;
