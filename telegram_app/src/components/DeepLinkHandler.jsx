import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTelegram } from "../context/TelegramContext";

/**
 * Mini App deep links via Telegram `start_param`.
 *
 * Supported tokens (set via `t.me/<bot>/<app>?startapp=<token>`):
 *
 *   room_<id>     → /rooms/<id>
 *   booking_<id>  → /me/bookings/<id>
 *
 * Mounted once near the router root; navigates exactly one time per session.
 */
function DeepLinkHandler() {
  const navigate = useNavigate();
  const { startParam } = useTelegram();

  useEffect(() => {
    if (!startParam) return;
    const consumedKey = "fh:start_param:consumed";
    if (sessionStorage.getItem(consumedKey) === startParam) return;
    sessionStorage.setItem(consumedKey, startParam);

    const [kind, idRaw] = startParam.split("_");
    const id = Number.parseInt(idRaw, 10);

    if (kind === "room" && Number.isFinite(id)) {
      navigate(`/rooms/${id}`);
    } else if (kind === "booking" && Number.isFinite(id)) {
      navigate(`/me/bookings/${id}`);
    }
  }, [startParam, navigate]);

  return null;
}

export default DeepLinkHandler;
