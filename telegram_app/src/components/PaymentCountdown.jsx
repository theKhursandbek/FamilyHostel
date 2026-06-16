import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Clock } from "lucide-react";

/**
 * MM:SS countdown for a payment hold (BookingDraft / ExtensionDraft).
 *
 * Why: when a client lands on the payment page, the backend has already
 * reserved the room+date window via a :class:`BookingDraft` with a 10-minute
 * TTL. We surface that deadline so the user knows they need to act.
 *
 * Behaviour
 * ─────────
 *   • Counts down once per second using ``Date.now()`` so a sleeping tab
 *     resyncs cleanly when it wakes.
 *   • Calls ``onExpire`` exactly once when the deadline passes.
 *   • Visual states:
 *       > 2 min  → muted text
 *       ≤ 2 min  → warning amber
 *       0        → "Hold expired" (no negative numbers shown).
 *
 * @param {string|Date} expiresAt  ISO-8601 string or Date — the deadline.
 * @param {() => void}  onExpire   Called once when the timer hits zero.
 */
export default function PaymentCountdown({ expiresAt, onExpire, variant = "full" }) {
  const { t } = useTranslation();
  const deadline = expiresAt instanceof Date
    ? expiresAt.getTime()
    : new Date(expiresAt).getTime();

  const [now, setNow] = useState(() => Date.now());
  const [fired, setFired] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(deadline)) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [deadline]);

  useEffect(() => {
    if (fired) return;
    if (Number.isFinite(deadline) && now >= deadline) {
      setFired(true);
      onExpire?.();
    }
  }, [now, deadline, fired, onExpire]);

  if (!Number.isFinite(deadline)) return null;

  const remainingMs = Math.max(0, deadline - now);
  const totalSecs = Math.floor(remainingMs / 1000);
  const mm = String(Math.floor(totalSecs / 60)).padStart(2, "0");
  const ss = String(totalSecs % 60).padStart(2, "0");

  const expired = remainingMs === 0;
  const warning = !expired && remainingMs <= 120_000;

  if (variant === "compact") {
    return (
      <div
        className={
          "payment-countdown payment-countdown--compact"
          + (warning ? " payment-countdown--warn" : "")
          + (expired ? " payment-countdown--expired" : "")
        }
        role="timer"
        aria-live="polite"
      >
        <strong>{mm}:{ss}</strong>
      </div>
    );
  }

  return (    <div
      className={
        "payment-countdown"
        + (warning ? " payment-countdown--warn" : "")
        + (expired ? " payment-countdown--expired" : "")
      }
      role="timer"
      aria-live="polite"
    >
      <Clock size={14} strokeWidth={1.8} />
      {expired ? (
        <span>{t("payment.hold_expired", "Hold expired")}</span>
      ) : (
        <span>
          {t("payment.hold_remaining", "Reserved for")}{" "}
          <strong>{mm}:{ss}</strong>
        </span>
      )}
    </div>
  );
}
