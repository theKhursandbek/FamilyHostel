/**
 * Strict guest-identity validators for the admin app.
 *
 * Ported 1:1 from the Telegram Mini App (telegram_app/src/utils/validators.js)
 * and the backend mirror (apps/common/validators.py) so the walk-in / booking
 * wizard rejects exactly what every other surface rejects.
 *
 * Each validator returns one of:
 *   { ok: true,  value }            — value is the *normalised* input
 *   { ok: false, message }          — human-readable English error
 *
 * Pure functions: no I/O, no side effects, never throw.
 */

const _str = (v) => (v == null ? "" : String(v));
const _trim = (v) => _str(v).trim();

const okv = (value) => ({ ok: true, value });
const fail = (message) => ({ ok: false, message });

// Name: Unicode letters only, 3-20 chars. NO spaces, hyphens, apostrophes, digits.
export const NAME_RE = /^\p{L}{3,20}$/u;
// Phone: strictly +998 followed by exactly 9 digits.
export const PHONE_RE = /^\+998\d{9}$/;
// Passport: exactly 2 uppercase Latin letters + exactly 7 digits.
export const PASSPORT_RE = /^[A-Z]{2}\d{7}$/;
// ISO calendar date.
export const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// ── Names ───────────────────────────────────────────────────────────────
export function validateName(raw, { min = 3, max = 20, label = "Name" } = {}) {
  // No spaces allowed anywhere — strip them before checking.
  const v = _str(raw).replace(/\s+/g, "");
  if (!v) return fail(`${label} is required.`);
  if (v.length < min) return fail(`${label} must be at least ${min} letters.`);
  if (v.length > max) return fail(`${label} must be at most ${max} letters.`);
  if (!NAME_RE.test(v)) return fail("Letters only, no spaces or symbols.");
  return okv(v);
}

/**
 * Live input mask for names: blocks every keystroke that isn't a Unicode
 * letter (no spaces, digits, or symbols ever reach the field) and forces the
 * very first letter to uppercase. Returns a value the user can keep typing.
 */
export function formatNameInput(raw, { max = 20 } = {}) {
  // Keep Unicode letters only — spaces, digits and symbols are dropped.
  let v = _str(raw).replace(/[^\p{L}]/gu, "");
  if (v.length > max) v = v.slice(0, max);
  if (v) v = v.charAt(0).toLocaleUpperCase() + v.slice(1);
  return v;
}

// ── Phone (Uzbekistan) ───────────────────────────────────────────────────
export function validatePhone(raw) {
  let cleaned = _str(raw).replace(/[^\d+]/g, "");
  if (!cleaned.startsWith("+") && cleaned.startsWith("998")) {
    cleaned = `+${cleaned}`;
  }
  if (!cleaned || cleaned === "+998") return fail("Phone number is required.");
  if (!PHONE_RE.test(cleaned)) {
    return fail("Phone must start with +998 and have 9 more digits.");
  }
  return okv(cleaned);
}

/**
 * Live input formatter: blocks every non-digit keystroke and auto-inserts
 * grouping spaces in real time → "+998 90 123 45 67". Always keeps the
 * "+998" prefix and at most 9 trailing digits. The spaces are cosmetic only —
 * validatePhone() strips them before checking, so the stored value stays
 * "+998901234567".
 */
export function formatPhoneInput(raw) {
  let digits = _str(raw).replace(/\D/g, "");
  if (digits.startsWith("998")) digits = digits.slice(3);
  digits = digits.slice(0, 9);
  if (!digits) return "+998";
  // Uzbek grouping: operator (2) · block (3) · pair (2) · pair (2).
  const groups = [
    digits.slice(0, 2),
    digits.slice(2, 5),
    digits.slice(5, 7),
    digits.slice(7, 9),
  ].filter(Boolean);
  return `+998 ${groups.join(" ")}`;
}

// ── Passport ──────────────────────────────────────────────────────────────
export function validatePassport(raw) {
  const v = _str(raw).toUpperCase().replace(/\s+/g, "");
  if (!v) return fail("Passport number is required.");
  if (!PASSPORT_RE.test(v)) {
    return fail("Passport must be 2 letters + 7 digits, e.g. AB1234567.");
  }
  return okv(v);
}

/** Live input mask: up to 2 leading uppercase letters, then up to 7 digits. */
export function formatPassportInput(raw) {
  const s = _str(raw).toUpperCase().replace(/[^A-Z0-9]/g, "");
  let letters = "";
  let digits = "";
  for (const ch of s) {
    if (ch >= "A" && ch <= "Z") {
      if (letters.length < 2) letters += ch; // extra letters are dropped
    } else if (ch >= "0" && ch <= "9") {
      // Block digits until exactly two letters have been entered first.
      if (letters.length === 2 && digits.length < 7) digits += ch;
    }
  }
  return letters + digits;
}

// ── Date of birth ─────────────────────────────────────────────────────────
/** Local-calendar today in YYYY-MM-DD (avoids UTC drift). */
export function todayLocalISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Latest allowed DOB for a given minimum age (inclusive) — for input `max`. */
export function maxDOBForAge(minAge = 16) {
  const d = new Date();
  d.setFullYear(d.getFullYear() - minAge);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * @param {string} iso  ISO date "YYYY-MM-DD"
 */
export function validateDOB(iso, { minAge = 16, maxAge = 120 } = {}) {
  const v = _trim(iso);
  if (!v) return fail("Date of birth is required.");
  if (!ISO_DATE_RE.test(v)) return fail("Enter a valid date.");
  const [y, m, d] = v.split("-").map(Number);
  const dob = new Date(y, m - 1, d);
  // Round-trip guard rejects impossible dates like 2023-02-31.
  if (dob.getFullYear() !== y || dob.getMonth() !== m - 1 || dob.getDate() !== d) {
    return fail("Enter a valid date.");
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (dob > today) return fail("Date of birth cannot be in the future.");
  let age = today.getFullYear() - y;
  const beforeBirthday =
    today.getMonth() < m - 1 ||
    (today.getMonth() === m - 1 && today.getDate() < d);
  if (beforeBirthday) age -= 1;
  if (age < minAge) return fail(`Guest must be at least ${minAge} years old.`);
  if (age > maxAge) return fail("Please enter a valid date of birth.");
  return okv(v);
}

// ── Date helpers (shared by the booking wizard) ───────────────────────────
export function addDaysISO(iso, days) {
  if (!iso) return "";
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * True when [inA, outA) overlaps [inB, outB) — half-open night intervals, so
 * a checkout day may equal the next guest's check-in day.
 */
export function rangesOverlap(inA, outA, inB, outB) {
  return inA < outB && outA > inB;
}

/**
 * Given the room's booked ranges (from the availability endpoint), return the
 * first range that overlaps the requested [checkIn, checkOut), or null.
 * Each range is `{ check_in_date, check_out_date }` (ISO strings).
 */
export function findOverlap(bookedRanges, checkIn, checkOut, { excludeId } = {}) {
  if (!checkIn || !checkOut) return null;
  for (const r of bookedRanges || []) {
    if (excludeId != null && r.id === excludeId) continue;
    if (rangesOverlap(checkIn, checkOut, r.check_in_date, r.check_out_date)) {
      return r;
    }
  }
  return null;
}
