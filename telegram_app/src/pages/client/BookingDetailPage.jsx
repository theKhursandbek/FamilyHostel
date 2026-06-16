import { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  CalendarDays, MapPin, BedDouble, Moon, Receipt, Hash,
  CalendarPlus, XCircle,
} from "lucide-react";

import { getBooking, cancelBooking } from "../../services/bookings";
import ConfirmDialog from "../../components/ConfirmDialog";
import BackButton from "../../components/BackButton";
import RoomCarousel from "../../components/RoomCarousel";
import { fmtDate, fmtDateTime, fmtMoney, daysBetween } from "../../utils/format";

const STATUS_KEY = {
  pending: "booking.status_pending",
  paid: "booking.status_paid",
  canceled: "booking.status_canceled",
  cancelled: "booking.status_canceled",
  completed: "booking.status_completed",
};

/**
 * Booking detail — every field about a booking, plus Cancel + Extend.
 *
 * Route is protected (see App.jsx), so the user is always authenticated
 * here and the canonical /bookings/my/<id>/ endpoint is used.
 */
export default function BookingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [working, setWorking] = useState(false);

  const fetchOne = useCallback(() => {
    setLoading(true);
    setError(null);
    getBooking(id)
      .then(setBooking)
      .catch((e) => setError(e?.response?.data?.detail || t("common.load_failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(fetchOne, [fetchOne]);

  const status = booking?.status;
  const cancellable = status === "pending" || status === "paid";
  const extendable = status === "paid";

  const lang = i18n.language;
  const fmtD = (s) => fmtDate(s, lang);
  const fmtDT = (s) => fmtDateTime(s, lang);
  const fmtM = (n) => fmtMoney(n, lang);
  const days = booking ? Math.max(1, daysBetween(booking.check_in_date, booking.check_out_date)) : 0;

  const handleCancelConfirmed = async () => {
    if (working) return;
    setWorking(true);
    try {
      const updated = await cancelBooking(id);
      setBooking(updated);
      setConfirmOpen(false);
    } catch (err) {
      setError(err?.response?.data?.detail || t("common.error"));
    } finally {
      setWorking(false);
    }
  };

  if (loading) return <div className="page-loading">{t("common.loading")}</div>;
  if (error && !booking) {
    return (
      <div className="page-error">
        <p>{error}</p>
        <button type="button" className="btn btn-primary" onClick={fetchOne}>
          {t("common.retry")}
        </button>
      </div>
    );
  }
  if (!booking) return null;

  return (
    <section className="booking-detail">
      <BackButton />
      <RoomCarousel
        images={(
          (booking.room_image_urls && booking.room_image_urls.length
            ? booking.room_image_urls
            : [booking.room_primary_image_url, booking.room_image_url].filter(Boolean))
        ).map((url, i) => ({ id: i, image_url: url }))}
        alt={t("room.title", "Room")}
      />
      <header className="booking-detail__header">
        <h1>{t("my_bookings.booking_no", { id: booking.id })}</h1>
        <span className={`badge badge--${status}`}>
          {t(STATUS_KEY[status] || "common.empty")}
        </span>
      </header>

      <ul className="booking-detail__list">
        <li>
          <span className="booking-detail__label">
            <Hash size={14} strokeWidth={1.8} /> {t("my_bookings.booking_id", "Booking ID")}
          </span>
          <span className="booking-detail__value">#{booking.id}</span>
        </li>
        <li>
          <span className="booking-detail__label">
            <BedDouble size={14} strokeWidth={1.8} /> {t("room.title", "Room")}
          </span>
          <span className="booking-detail__value">
            № {booking.room_number || booking.room}
          </span>
        </li>
        <li>
          <span className="booking-detail__label">
            <MapPin size={14} strokeWidth={1.8} /> {t("filter.branch", "Branch")}
          </span>
          <span className="booking-detail__value">{booking.branch_name || "—"}</span>
        </li>
        <li>
          <span className="booking-detail__label">
            <CalendarDays size={14} strokeWidth={1.8} /> {t("booking.check_in")}
          </span>
          <span className="booking-detail__value">{fmtD(booking.check_in_date)}</span>
        </li>
        <li>
          <span className="booking-detail__label">
            <CalendarDays size={14} strokeWidth={1.8} /> {t("booking.check_out")}
          </span>
          <span className="booking-detail__value">{fmtD(booking.check_out_date)}</span>
        </li>
        <li>
          <span className="booking-detail__label">
            <Moon size={14} strokeWidth={1.8} /> {t("booking.nights")}
          </span>
          <span className="booking-detail__value">
            {t("booking.days_count", { count: days, defaultValue: "{{count}} kun" })}
          </span>
        </li>
        <li>
          <span className="booking-detail__label">
            <Receipt size={14} strokeWidth={1.8} /> {t("booking.price_per_night")}
          </span>
          <span className="booking-detail__value">{fmtM(booking.room_base_price)}</span>
        </li>
        {Number(booking.discount_amount) > 0 && (
          <li>
            <span className="booking-detail__label">
              {t("booking.discount", "Discount")}
            </span>
            <span className="booking-detail__value">−{fmtM(booking.discount_amount)}</span>
          </li>
        )}
        <li className="booking-detail__total">
          <span className="booking-detail__label">{t("booking.total")}</span>
          <span className="booking-detail__value">{fmtM(booking.final_price)}</span>
        </li>
        <li>
          <span className="booking-detail__label">{t("booking.paid", "Paid")}</span>
          <span className="booking-detail__value">{fmtM(booking.paid_total)}</span>
        </li>
        {Number(booking.balance_due) > 0 && (
          <li>
            <span className="booking-detail__label">{t("booking.balance", "Balance due")}</span>
            <span className="booking-detail__value">{fmtM(booking.balance_due)}</span>
          </li>
        )}
        <li>
          <span className="booking-detail__label">{t("booking.created_at", "Created")}</span>
          <span className="booking-detail__value">{fmtDT(booking.created_at)}</span>
        </li>
      </ul>

      {error && <div className="form-error" role="alert">{error}</div>}

      <div className="booking-detail__actions">
        {extendable && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/me/bookings/${id}/extend`)}
          >
            <CalendarPlus size={16} strokeWidth={1.8} />
            {t("my_bookings.extend", "Extend")}
          </button>
        )}
        {cancellable && (
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setConfirmOpen(true)}
          >
            <XCircle size={16} strokeWidth={1.8} />
            {t("booking.cancel", "Cancel")}
          </button>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={t("booking.cancel_title")}
        message={t("booking.cancel_warning")}
        confirmLabel={t("booking.cancel_confirm_button")}
        cancelLabel={t("common.no")}
        destructive
        loading={working}
        onConfirm={handleCancelConfirmed}
        onCancel={() => !working && setConfirmOpen(false)}
      />
    </section>
  );
}
