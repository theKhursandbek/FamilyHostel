import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BedDouble, MapPin } from "lucide-react";

import RoomCarousel from "../../components/RoomCarousel";
import BackButton from "../../components/BackButton";
import { Loader, ErrorBox } from "../../components/Status";
import { useAuth } from "../../context/AuthContext";
import { useTelegram } from "../../context/TelegramContext";
import useMainButton from "../../hooks/useMainButton";
import { getRoom } from "../../services/catalogue";

/**
 * Room detail — carousel + facts + sticky "Book" CTA.
 *
 * Plan: §1.5 (carousel parity), §5.6 (Book wired through MainButton).
 */
function RoomDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const { hapticImpact } = useTelegram();

  const [room, setRoom] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRoom = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRoom(await getRoom(id));
    } catch (err) {
      setError(err?.response?.data?.error?.message || t("common.error", "Something went wrong."));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    fetchRoom();
  }, [fetchRoom]);

  const isClient = user?.roles?.includes("client");
  const canBook = room?.status === "available";

  const onBook = useCallback(() => {
    hapticImpact?.("medium");
    // Booking flow is temporarily open to guests — no login required.
    if (!isAuthenticated || isClient) {
      navigate(`/book/${room.id}`);
    } else {
      navigate("/me");
    }
  }, [hapticImpact, isAuthenticated, isClient, navigate, room]);

  useMainButton({
    text: t("room.book_now", "Book now"),
    visible: !!room,
    disabled: !canBook,
    onClick: onBook,
  });

  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={fetchRoom} />;
  if (!room) return null;

  const locationLabel = room.branch?.location_label || room.branch_location_label || "";
  const branchName = room.branch?.name || room.branch_name;
  const typeName = room.room_type?.name || room.room_type_name;

  return (
    <div className="room-detail">
      <BackButton />

      <RoomCarousel images={room.images || []} alt={`Room ${room.room_number}`} />

      <header className="room-detail__header">
        <h1 className="room-detail__title">№ {room.room_number}</h1>
        <div className="room-detail__price">
          {Number(room.base_price).toLocaleString("uz-UZ")}{" "}
          <small>
            {t("common.currency_uzs", "UZS")} / {t("common.night", "night")}
          </small>
        </div>
      </header>

      <p className="room-detail__meta">
        <BedDouble size={14} strokeWidth={1.8} aria-hidden="true" /> {typeName}
        <span className="room-detail__sep">·</span>
        <MapPin size={14} strokeWidth={1.8} aria-hidden="true" /> {branchName}
        {locationLabel ? `, ${locationLabel}` : ""}
      </p>

      {!canBook ? (
        <div className="room-detail__notice">
          {t("room.unavailable", "This room is not available right now.")}
        </div>
      ) : null}

      {/* Fallback CTA for desktop / browsers without Telegram MainButton. */}
      <button
        type="button"
        className="btn btn--primary room-detail__cta"
        onClick={onBook}
        disabled={!canBook}
      >
        {t("room.book_now", "Book now")}
      </button>
    </div>
  );
}

export default RoomDetailPage;
