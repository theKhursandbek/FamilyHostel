/**
 * Strict client-side validators for the Mini App.
 *
 * Mirrors the backend vocabulary in ``apps/common/validators.py`` so the
 * error codes ("invalid_phone", "weak_password", "range_inverted", …) line
 * up across surfaces. Every validator returns one of:
 *
 *   { ok: true,  value }           — value is the *normalised* input
 *   { ok: false, code, messageKey, params? }
 *
 * Callers translate ``messageKey`` via ``t(messageKey, fallback, params)``.
 *
 * Design rules:
 *   - Pure (no I/O, no side effects).
 *   - Forgiving on input *type* (accept null/undefined → treated as empty).
 *   - Strict on output (always return the cleaned value to be sent to the
 *     server, never the raw user string).
 *   - Never throw — always return the result envelope.
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ok = (value) => ({ ok: true, value });
const fail = (code, messageKey, params) => ({
  ok: false,
  code,
  messageKey,
  ...(params ? { params } : {}),
});

const _str = (v) => (v == null ? "" : String(v));
const _trim = (v) => _str(v).trim();

// Name: Unicode letters only, 3-20 chars. NO spaces, hyphens, apostrophes, digits.
const NAME_RE = /^\p{L}{3,20}$/u;

// Phone: strictly +998 followed by exactly 9 digits.
const PHONE_RE = /^\+998\d{9}$/;

// Passport: exactly 2 uppercase Latin letters + exactly 7 digits.
const PASSPORT_RE = /^[A-Z]{2}\d{7}$/;

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// ---------------------------------------------------------------------------
// Names
// ---------------------------------------------------------------------------

export function validateName(raw, { min = 3, max = 20 } = {}) {
  // No spaces allowed anywhere — strip them before checking.
  const v = _str(raw).replace(/\s+/g, "");
  if (!v) return fail("required", "validation.required");
  if (v.length < min) return fail("min_length", "validation.name_min", { min });
  if (v.length > max) return fail("max_length", "validation.name_max", { max });
  if (!NAME_RE.test(v)) return fail("invalid_name", "validation.invalid_name");
  return ok(v);
}

// ---------------------------------------------------------------------------
// Phone
// ---------------------------------------------------------------------------

export function validatePhone(raw) {
  // Strip everything except digits and the leading '+'.
  let cleaned = _str(raw).replace(/[^\d+]/g, "");
  // Tolerate "998..." without leading '+'.
  if (!cleaned.startsWith("+") && cleaned.startsWith("998")) {
    cleaned = `+${cleaned}`;
  }
  if (!cleaned) return fail("required", "validation.required");
  if (!PHONE_RE.test(cleaned)) return fail("invalid_phone", "validation.invalid_phone");
  return ok(cleaned);
}

/**
 * Live input formatter for the phone field: returns a string the user can
 * keep typing into. Ensures the value always starts with "+998" and
 * contains at most 9 trailing digits.
 */
export function formatPhoneInput(raw) {
  // Drop everything except digits.
  let digits = _str(raw).replace(/\D/g, "");
  // If the user typed "+998..." or "998...", strip the country code so we
  // can reattach it cleanly.
  if (digits.startsWith("998")) digits = digits.slice(3);
  digits = digits.slice(0, 9);
  return digits ? `+998${digits}` : "+998";
}

// ---------------------------------------------------------------------------
// Date of birth
// ---------------------------------------------------------------------------

/**
 * @param {string} iso  ISO date "YYYY-MM-DD"
 */
export function validateDOB(iso, { minAge = 16, maxAge = 120 } = {}) {
  const v = _trim(iso);
  if (!v) return fail("required", "validation.required");
  if (!ISO_DATE_RE.test(v)) return fail("invalid_date", "validation.invalid_date");
  const [y, m, d] = v.split("-").map(Number);
  const dob = new Date(y, m - 1, d);
  if (dob.getFullYear() !== y || dob.getMonth() !== m - 1 || dob.getDate() !== d) {
    return fail("invalid_date", "validation.invalid_date");
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (dob > today) return fail("dob_in_future", "validation.dob_in_future");
  // Age in completed years.
  let age = today.getFullYear() - y;
  const beforeBirthday =
    today.getMonth() < m - 1 ||
    (today.getMonth() === m - 1 && today.getDate() < d);
  if (beforeBirthday) age -= 1;
  if (age < minAge) return fail("min_age", "validation.min_age", { min: minAge });
  if (age > maxAge) return fail("max_age", "validation.max_age", { max: maxAge });
  return ok(v);
}

// ---------------------------------------------------------------------------
// Passport
// ---------------------------------------------------------------------------

export function validatePassport(raw) {
  // Strip ALL whitespace, force uppercase.
  // Then must be exactly 2 uppercase letters + exactly 7 digits.
  const v = _str(raw).toUpperCase().replace(/\s+/g, "");
  if (!v) return fail("required", "validation.required");
  if (!PASSPORT_RE.test(v)) return fail("invalid_passport", "validation.invalid_passport");
  return ok(v);
}

// ---------------------------------------------------------------------------
// Password
// ---------------------------------------------------------------------------

export function validatePassword(raw, { min = 8, max = 128, requireMixed = true } = {}) {
  const v = _str(raw); // do NOT trim — leading/trailing chars are valid in pwd
  if (!v) return fail("required", "validation.required");
  if (v.length < min) return fail("min_length", "validation.password_min", { min });
  if (v.length > max) return fail("max_length", "validation.max_length", { max });
  if (requireMixed) {
    const hasLetter = /\p{L}/u.test(v);
    const hasDigit = /\d/.test(v);
    if (!hasLetter || !hasDigit) {
      return fail("weak_password", "validation.weak_password");
    }
  }
  return ok(v);
}

/** Loose login-time password check (server already enforces the real rule). */
export function validateLoginPassword(raw, { min = 6, max = 128 } = {}) {
  const v = _str(raw);
  if (!v) return fail("required", "validation.required");
  if (v.length < min) return fail("min_length", "validation.password_min", { min });
  if (v.length > max) return fail("max_length", "validation.max_length", { max });
  return ok(v);
}

/** Telegram OTP: exactly 6 digits. */
export function validateOtpCode(raw) {
  const v = _str(raw).replace(/\s/g, "");
  if (!v) return fail("required", "validation.required");
  if (!/^\d{6}$/.test(v)) return fail("invalid_otp", "validation.invalid_otp");
  return ok(v);
}

export function validateMatch(a, b, { messageKey = "validation.passwords_dont_match" } = {}) {
  if (a === b) return ok(a);
  return fail("mismatch", messageKey);
}

// ---------------------------------------------------------------------------
// Dates / date ranges
// ---------------------------------------------------------------------------

/** Local-calendar today in YYYY-MM-DD (avoids UTC drift). */
export function todayLocalISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Latest allowed DOB for a given minimum age (inclusive). */
export function maxDOBForAge(minAge = 16) {
  const d = new Date();
  d.setFullYear(d.getFullYear() - minAge);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function validateDate(iso, { allowPast = true, field = "date" } = {}) {
  const v = _trim(iso);
  if (!v) return fail("required", "validation.required");
  if (!ISO_DATE_RE.test(v)) return fail("invalid_date", "validation.invalid_date");
  const [y, m, d] = v.split("-").map(Number);
  const parsed = new Date(y, m - 1, d);
  if (parsed.getFullYear() !== y || parsed.getMonth() !== m - 1 || parsed.getDate() !== d) {
    return fail("invalid_date", "validation.invalid_date");
  }
  if (!allowPast && v < todayLocalISO()) {
    return fail("date_in_past", "validation.date_in_past");
  }
  return ok(v);
}

/**
 * Validate an inclusive [start, end] date range with a min/max night count.
 * Returns ``{ ok, value: { start, end, nights } }`` on success.
 */
export function validateDateRange(start, end, { minNights = 1, maxNights = 365, allowStartInPast = false } = {}) {
  const s = validateDate(start, { allowPast: allowStartInPast });
  if (!s.ok) return { ...s, field: "start" };
  const e = validateDate(end, { allowPast: true });
  if (!e.ok) return { ...e, field: "end" };
  const a = new Date(s.value);
  const b = new Date(e.value);
  const nights = Math.round((b - a) / 86_400_000);
  if (nights < minNights) {
    return fail("min_nights", "validation.min_nights", { min: minNights });
  }
  if (nights > maxNights) {
    return fail("max_nights", "validation.max_nights", { max: maxNights });
  }
  return ok({ start: s.value, end: e.value, nights });
}

// ---------------------------------------------------------------------------
// Numbers / money / ranges
// ---------------------------------------------------------------------------

/**
 * Returns a *cleaned* digit-only string (suitable for re-displaying in the
 * input) plus the parsed integer. Empty input is allowed (value = null).
 */
export function validateInt(raw, { min = 0, max = 1_000_000_000, allowEmpty = true } = {}) {
  const cleaned = _str(raw).replace(/[^\d]/g, "");
  if (!cleaned) {
    if (allowEmpty) return ok({ display: "", number: null });
    return fail("required", "validation.required");
  }
  // Cap typed length so we never construct huge BigInts.
  const trimmed = cleaned.slice(0, String(max).length + 1);
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return fail("invalid", "validation.invalid_number");
  if (n < min) return fail("min_value", "validation.min_value", { min });
  if (n > max) return fail("max_value", "validation.max_value", { max });
  return ok({ display: String(n), number: n });
}

/**
 * Validate a price-range pair. Either side may be empty. Returns the
 * normalised pair plus a flag if the range is inverted.
 */
export function validatePriceRange(rawMin, rawMax, opts = {}) {
  const lo = validateInt(rawMin, opts);
  if (!lo.ok) return { ...lo, field: "min" };
  const hi = validateInt(rawMax, opts);
  if (!hi.ok) return { ...hi, field: "max" };
  if (lo.value.number != null && hi.value.number != null && lo.value.number > hi.value.number) {
    return fail("range_inverted", "validation.range_inverted");
  }
  return ok({ min: lo.value, max: hi.value });
}
