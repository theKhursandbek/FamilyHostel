import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { WifiOff } from "lucide-react";

/**
 * Fixed top banner that appears when the device loses network connectivity.
 * Listens to the native browser online/offline events — no polling.
 */
export default function OfflineBanner() {
  const { t } = useTranslation();
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline  = () => setOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online",  goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online",  goOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div className="offline-banner" role="alert" aria-live="assertive">
      <WifiOff size={14} strokeWidth={2} aria-hidden="true" />
      {t("common.offline", "No internet connection")}
    </div>
  );
}
