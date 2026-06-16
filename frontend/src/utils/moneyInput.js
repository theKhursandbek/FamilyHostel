/**
 * Shared helpers for money/digit-only inputs across all roles.
 *
 * Pattern:
 *   <input
 *     type="text"
 *     inputMode="numeric"
 *     value={fmtMoney(state)}
 *     onChange={(e) => setState(fmtMoney(e.target.value))}
 *   />
 *   // before sending to API:
 *   const value = rawMoney(state);  // → "1000000"
 */

/** Strip all spacing characters (regular + non-breaking) → digits only string. */
export const rawMoney = (s) =>
  String(s ?? "").replace(/[\s\u00a0]/g, "").replace(/\D/g, "");

/**
 * Format a digit string with narrow non-breaking spaces every 3 digits.
 * e.g. "1000000" → "1\u00a0000\u00a0000"
 */
export const fmtMoney = (s) => {
  const d = rawMoney(s);
  return d ? d.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0") : "";
};
