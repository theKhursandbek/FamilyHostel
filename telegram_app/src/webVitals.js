/**
 * Web-vitals beacon.
 *
 * If the optional `web-vitals` dependency is installed, lazy-imports it and
 * pipes Core Web Vitals (LCP, CLS, INP, FCP, TTFB) to the backend
 * `/metrics/web-vitals/` sink. Without the dep, falls back to a minimal
 * Performance API observer reporting LCP and FCP only.
 *
 * Designed to be fire-and-forget — never throws, never blocks, uses
 * `navigator.sendBeacon` when available so it survives page unload.
 */

const ENDPOINT = (() => {
  const base = import.meta.env.VITE_API_URL || "/api/v1";
  return `${base.replace(/\/$/, "")}/metrics/web-vitals/`;
})();

function beacon(payload) {
  try {
    const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
    if (navigator.sendBeacon && navigator.sendBeacon(ENDPOINT, blob)) return;
  } catch {
    /* fall through */
  }
  try {
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* swallow */
  }
}

function fallbackObserver() {
  if (typeof PerformanceObserver !== "function") return;
  try {
    const lcpObs = new PerformanceObserver((list) => {
      const last = list.getEntries().pop();
      if (last) {
        beacon({ name: "LCP", value: last.startTime, id: `lcp-${Date.now()}` });
      }
    });
    lcpObs.observe({ type: "largest-contentful-paint", buffered: true });
  } catch { /* unsupported */ }
  try {
    const fcp = performance.getEntriesByName("first-contentful-paint")[0];
    if (fcp) beacon({ name: "FCP", value: fcp.startTime, id: `fcp-${Date.now()}` });
  } catch { /* ignore */ }
}

export function initWebVitals() {
  if (typeof window === "undefined") return;
  if (!import.meta.env.PROD) return; // dev → noisy, skip

  const moduleName = "web-vitals";
  import(/* @vite-ignore */ moduleName)
    .then(({ onLCP, onCLS, onINP, onFCP, onTTFB }) => {
      const handler = (m) => beacon({
        name: m.name, value: m.value, id: m.id,
        rating: m.rating, navigationType: m.navigationType,
      });
      onLCP(handler); onCLS(handler); onINP(handler); onFCP(handler); onTTFB(handler);
    })
    .catch(fallbackObserver);
}
