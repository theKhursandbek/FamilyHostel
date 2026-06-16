import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MapPin, BedDouble } from "lucide-react";

/**
 * Catalogue card. Mirrors the website's room card silhouette but tuned for
 * a Telegram WebView (full-bleed photo, soft shadow, 18 px radius).
 *
 * Plan: §1.3 — photo · room# · type · price · branch · location.
 */
function RoomCard({ room }) {
  const { t } = useTranslation();
  const photo = room?.primary_image_url || room?.images?.[0]?.image_url;
  const locationLabel = room?.branch_location_label || room?.branch_location || "";

  return (
    <Link to={`/rooms/${room.id}`} className="room-card" aria-label={room.room_number}>
      <div className="room-card__media">
        {photo ? (
          <img src={photo} alt={room.room_number} loading="lazy" />
        ) : (
          <div className="room-card__placeholder" aria-hidden="true">
            <BedDouble size={42} strokeWidth={1.4} />
          </div>
        )}
        {room.room_type_name ? (
          <span className="room-card__chip">{room.room_type_name}</span>
        ) : null}
      </div>
      <div className="room-card__body">
        <div className="room-card__title-row">
          <h3 className="room-card__title">№ {room.room_number}</h3>
          <span className="room-card__price">
            {Number(room.base_price).toLocaleString("uz-UZ")}{" "}
            <small>{t("common.currency_uzs", "UZS")}</small>
          </span>
        </div>
        <p className="room-card__branch">
          <MapPin size={14} strokeWidth={1.8} style={{ verticalAlign: "-2px" }} />{" "}
          {room.branch_name}
          {locationLabel ? <span className="room-card__location"> · {locationLabel}</span> : null}
        </p>
      </div>
    </Link>
  );
}

export default RoomCard;
