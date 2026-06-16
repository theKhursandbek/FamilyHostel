/**
 * Locale-aware formatting helpers shared across pages.
 *
 * The Mini App uses i18next language codes (`uz`, `ru`, `en`). Most JS
 * runtimes ship full ICU data only for major locales — Uzbek often falls
 * back to a useless numeric format like "2007 M06 13". To guarantee a
 * readable result on every device (Android Telegram WebView in
 * particular), we format Uzbek manually instead of trusting `Intl`.
 */

const UZ_MONTHS_SHORT = [
  "Yan", "Fev", "Mar", "Apr", "May", "Iyun",
  "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek",
];
const UZ_MONTHS_LONG = [
  "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
  "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
];

function isUz(lang) {
  return (lang || "").slice(0, 2).toLowerCase() === "uz";
}

export function localeFor(lang) {
  switch ((lang || "").slice(0, 2).toLowerCase()) {
    case "ru": return "ru-RU";
    case "en": return "en-GB";
    default:   return "en-GB";
  }
}

const DATE_OPTS = { day: "2-digit", month: "short", year: "numeric" };
const DATETIME_OPTS = {
  day: "2-digit", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit",
};

const pad2 = (n) => String(n).padStart(2, "0");

function toDate(value) {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtDate(value, lang) {
  const d = toDate(value);
  if (!d) return "—";
  if (isUz(lang)) {
    return `${pad2(d.getDate())}-${UZ_MONTHS_SHORT[d.getMonth()]} ${d.getFullYear()}`;
  }
  try {
    return d.toLocaleDateString(localeFor(lang), DATE_OPTS);
  } catch {
    return d.toLocaleDateString("en-GB", DATE_OPTS);
  }
}

export function fmtDateTime(value, lang) {
  const d = toDate(value);
  if (!d) return "—";
  if (isUz(lang)) {
    return `${pad2(d.getDate())}-${UZ_MONTHS_SHORT[d.getMonth()]} ${d.getFullYear()}, ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  }
  try {
    return d.toLocaleString(localeFor(lang), DATETIME_OPTS);
  } catch {
    return d.toLocaleString("en-GB", DATETIME_OPTS);
  }
}

export function fmtDateLong(value, lang) {
  const d = toDate(value);
  if (!d) return "—";
  if (isUz(lang)) {
    return `${d.getDate()}-${UZ_MONTHS_LONG[d.getMonth()]} ${d.getFullYear()}`;
  }
  try {
    return d.toLocaleDateString(localeFor(lang), { day: "numeric", month: "long", year: "numeric" });
  } catch {
    return fmtDate(value, lang);
  }
}

export function fmtMoney(value, lang, currency = "UZS") {
  const n = Number(value || 0);
  // Uzbek number formatting uses non-breaking spaces as thousand
  // separators, which Intl handles fine on most engines, but to keep the
  // visual identical across runtimes we format manually for `uz`.
  if (isUz(lang)) {
    const grouped = Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return `${grouped} ${currency}`;
  }
  try {
    return `${n.toLocaleString(localeFor(lang))} ${currency}`;
  } catch {
    return `${n} ${currency}`;
  }
}

/** Whole-day diff between two YYYY-MM-DD or Date values (rounded, min 0). */
export function daysBetween(start, end) {
  if (!start || !end) return 0;
  const a = start instanceof Date ? start : new Date(start);
  const b = end instanceof Date ? end : new Date(end);
  const diff = Math.round((b - a) / 86_400_000);
  return diff > 0 ? diff : 0;
}
