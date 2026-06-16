import { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MapPin, Moon, CalendarPlus, XCircle } from "lucide-react";

import { listMyBookings, cancelBooking } from "../../services/bookings";
import ConfirmDialog from "../../components/ConfirmDialog";
import { fmtDate, fmtMoney, daysBetween } from "../../utils/format";
import usePullToRefresh from "../../hooks/usePullToRefresh";

const STATUS_KEY = {
  pending: "booking.status_pending",
  paid: "booking.status_paid",
  canceled: "booking.status_canceled",
  cancelled: "booking.status_canceled",
  completed: "booking.status_completed",
};

/**
 * My bookings — two tabs: Active (pending + paid) · Past (canceled + completed).
 *
 * Authenticated-only (guarded by ProtectedRoute in App.jsx). Hits the
 * /bookings/my/ endpoint which returns the caller's full booking history,
 * so cancelled bookings stay visible in the Past tab forever.
 */
export default function MyBookingsPage() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("active");
  const [cancellingId, setCancellingId] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBookings(await listMyBookings());
    } catch (err) {
      setError(err?.response?.data?.detail || t("common.load_failed"));
    } finally {
      setLoading(false);
    }
    // Intentionally NOT depending on `t`: it changes on language switch,
    // which would re-trigger the fetch and flash a loading state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Pull-to-refresh
  const { containerRef, pullDistance, isPulling, isRefreshing } = usePullToRefresh({
    onRefresh: fetchAll,
  });

  const requestCancel = useCallback((e, bookingId) => {
    e.stopPropagation();
    setConfirmId(bookingId);
  }, []);

  const performCancel = useCallback(async () => {
    if (confirmId == null) return;
    setCancellingId(confirmId);
    try {
      await cancelBooking(confirmId);
      await fetchAll();
      setConfirmId(null);
    } catch (err) {
      setError(err?.response?.data?.detail || t("booking.cancel_failed", "Bekor qilib bo\u2018lmadi."));
    } finally {
      setCancellingId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmId, fetchAll]);

  const handleExtend = useCallback((e, bookingId) => {
    e.stopPropagation();
    navigate(`/me/bookings/${bookingId}/extend`);
  }, [navigate]);

  // Auto-refresh on focus / visibility / custom event from the booking flow.
  useEffect(() => {
    const refresh = () => { fetchAll(); };
    const onVisibility = () => { if (!document.hidden) fetchAll(); };
    window.addEventListener("focus", refresh);
    window.addEventListener("bookings:changed", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("bookings:changed", refresh);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [fetchAll]);

  const { active, past } = useMemo(() => {
    const a = [];
    const p = [];
    for (const b of bookings) {
      if (b.status === "pending" || b.status === "paid") a.push(b);
      else p.push(b);
    }
    return { active: a, past: p };
  }, [bookings]);

  const visible = tab === "active" ? active : past;

  if (loading) return <div className="page-loading">{t("common.loading")}</div>;
  if (error) {
    return (
      <div className="page-error">
        <p>{error}</p>
        <button type="button" className="btn btn-primary" onClick={fetchAll}>
          {t("common.retry")}
        </button>
      </div>
    );
  }

  return (
    <section className="my-bookings" ref={containerRef}>
      {/* Pull-to-refresh indicator */}
      <div
        className="ptr-indicator"
        style={{ height: isPulling || isRefreshing ? Math.min(pullDistance * 0.6, 48) : 0 }}
        aria-hidden="true"
      >
        {isRefreshing
          ? <span className="ptr-indicator__spinner" />
          : isPulling
            ? <span className="ptr-indicator__arrow" style={{ transform: `rotate(${Math.min(pullDistance / 65, 1) * 180}deg)` }}>↓</span>
            : null}
      </div>
      <header className="my-bookings__header">
        <h1>{t("my_bookings.title")}</h1>
      </header>

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "active"}
          className={`tab ${tab === "active" ? "is-active" : ""}`}
          onClick={() => setTab("active")}
        >
          {t("my_bookings.tab_active")} ({active.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "past"}
          className={`tab ${tab === "past" ? "is-active" : ""}`}
          onClick={() => setTab("past")}
        >
          {t("my_bookings.tab_past")} ({past.length})
        </button>
      </div>

      {visible.length === 0 ? (
        <div className="empty-state">
          <p>{t("booking.no_bookings")}</p>
          <button type="button" className="btn btn-primary" onClick={() => navigate("/")}>
            {t("booking.browse_rooms")}
          </button>
        </div>
      ) : (
        <ul className="booking-list">
          {visible.map((b) => {
            const days = Math.max(1, daysBetween(b.check_in_date, b.check_out_date));
            return (
              <li key={b.id}>
                <div
                  className="booking-card booking-card--rich"
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/me/bookings/${b.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      navigate(`/me/bookings/${b.id}`);
                    }
                  }}
                >
                  <div className="booking-card__body">
                    <div className="booking-card__top">
                      <strong>{t("room.room_number", { n: b.room_number || b.room })}</strong>
                      <span className={`badge badge--${b.status}`}>
                        {t(STATUS_KEY[b.status] || "common.empty")}
                      </span>
                    </div>
                    {b.branch_name && (
                      <div className="booking-card__sub">
                        <MapPin size={12} strokeWidth={1.8} style={{ verticalAlign: "-2px" }} />{" "}
                        {b.branch_name}
                      </div>
                    )}
                    <div className="booking-card__dates">
                      {fmtDate(b.check_in_date, i18n.language)} → {fmtDate(b.check_out_date, i18n.language)}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
                      <span className="booking-card__nights">
                        <Moon size={12} strokeWidth={1.8} />
                        {t("booking.days_count", { count: days, defaultValue: "{{count}} kun" })}
                      </span>
                      <span className="booking-card__total">
                        {fmtMoney(b.final_price, i18n.language)}
                      </span>
                    </div>
                    {tab === "active" && (b.status === "pending" || b.status === "paid") && (
                      <div className="booking-card__actions">
                        {b.status === "paid" && (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={(e) => handleExtend(e, b.id)}
                          >
                            <CalendarPlus size={16} strokeWidth={1.8} />
                            {t("my_bookings.extend", "Extend")}
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-danger"
                          onClick={(e) => requestCancel(e, b.id)}
                          disabled={cancellingId === b.id}
                        >
                          <XCircle size={16} strokeWidth={1.8} />
                          {cancellingId === b.id
                            ? t("common.loading", "\u2026")
                            : t("booking.cancel", "Cancel")}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <ConfirmDialog
        open={confirmId != null}
        title={t("booking.cancel_title")}
        message={t("booking.cancel_warning")}
        confirmLabel={t("booking.cancel_confirm_button")}
        cancelLabel={t("common.no")}
        destructive
        loading={cancellingId === confirmId}
        onConfirm={performCancel}
        onCancel={() => cancellingId == null && setConfirmId(null)}
      />
    </section>
  );
}
