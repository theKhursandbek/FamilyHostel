/**
 * Sentry initialization for the Telegram Mini App.
 *
 * Activated only when ``VITE_SENTRY_DSN`` is set at build time.
 * Sentry SDK is imported dynamically so the production bundle is not
 * inflated when telemetry is disabled.
 *
 * Usage:
 *   import { initSentry, captureException } from "./sentry";
 *   initSentry();
 *
 * Inside Telegram, ``release`` is tagged with the Mini App version and
 * ``environment`` is taken from VITE_ENV (defaults to "production").
 */

let _sentry = null;

export async function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return null;
  try {
    const Sentry = await import("@sentry/browser");
    Sentry.init({
      dsn,
      environment: import.meta.env.VITE_ENV || "production",
      release: import.meta.env.VITE_APP_VERSION || "hotel-mini-app@dev",
      tracesSampleRate: 0.1,
      // Telegram WebView occasionally surfaces noisy ResizeObserver
      // warnings — drop them to keep the issue tracker clean.
      ignoreErrors: [
        "ResizeObserver loop limit exceeded",
        "ResizeObserver loop completed with undelivered notifications.",
      ],
    });
    _sentry = Sentry;
    return Sentry;
  } catch (err) {
    console.warn("[sentry] init failed:", err);
    return null;
  }
}

export function captureException(err, context = {}) {
  if (!_sentry) return;
  try {
    _sentry.withScope((scope) => {
      Object.entries(context).forEach(([k, v]) => scope.setExtra(k, v));
      _sentry.captureException(err);
    });
  } catch {
    // Never let telemetry errors break the app.
  }
}

export function setUser(user) {
  if (!_sentry || !user) return;
  try {
    _sentry.setUser({
      id: String(user.account_id || user.telegram_id || ""),
      username: user.full_name,
    });
  } catch {
    // ignore
  }
}
