import { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { useTranslation } from "react-i18next";
import { SlidersHorizontal, Banknote, BedDouble, MapPin } from "lucide-react";
import { listLocations, listRoomTypes } from "../services/catalogue";
import { validateInt, validatePriceRange } from "../utils/validators";

/**
 * Catalogue filter bar — live, always-visible price inputs + a toggle that
 * reveals the room-type and location chip groups underneath.
 *
 *   ┌──────────────────────────────────────────┐  ┌────┐
 *   │ ✨  From _____   To _____               │  │ ☷  │  ← always visible
 *   └──────────────────────────────────────────┘  └────┘
 *
 *   When the toggle is on, each section below appears as its own card with
 *   a small brass icon header and a "Reset" link in the top-right corner.
 *
 * Filter changes are applied **immediately** (debounced for the price
 * inputs); there is no Apply button.
 */
function FilterBar({ value, onApply }) {
  const { t } = useTranslation();
  const [roomTypes, setRoomTypes] = useState([]);
  const [locations, setLocations] = useState([]);
  const [open, setOpen] = useState(false);

  // Local draft — kept in sync with the parent so a parent-level reset
  // (e.g. browser back) propagates back into the inputs.
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  // Debounce price changes so we don't fire a request on every keystroke.
  const debounceRef = useRef(null);
  const scheduleApply = (next) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => onApply(next), 250);
  };
  useEffect(() => () => debounceRef.current && clearTimeout(debounceRef.current), []);

  useEffect(() => {
    let mounted = true;
    Promise.all([listRoomTypes(), listLocations()])
      .then(([rt, loc]) => {
        if (!mounted) return;
        setRoomTypes(rt);
        setLocations(loc);
      })
      .catch(() => { /* silent — filters just hide */ });
    return () => { mounted = false; };
  }, []);

  // ---------------- handlers ----------------
  const setPrice = (key, raw) => {
    // Strict numeric input — strip non-digits and cap at 1B (9 digits) so we
    // never push pathological numbers to the backend.
    const result = validateInt(raw, { min: 0, max: 1_000_000_000, allowEmpty: true });
    const cleaned = result.ok ? result.value.display : "";
    const next = { ...draft, [key]: cleaned };
    setDraft(next);
    // Only schedule a server fetch if the resulting range is *valid*; an
    // inverted range (min > max) would be rejected by the backend with
    // ``range_inverted`` — surface the error inline instead of round-tripping.
    const rangeCheck = validatePriceRange(next.priceMin, next.priceMax);
    if (rangeCheck.ok) scheduleApply(next);
  };

  const toggle = (key, id) => {
    const arr = new Set(draft[key] ?? []);
    if (arr.has(id)) arr.delete(id);
    else arr.add(id);
    const next = { ...draft, [key]: Array.from(arr) };
    setDraft(next);
    onApply(next); // chips: apply immediately
  };

  const resetPrice = () => {
    const next = { ...draft, priceMin: "", priceMax: "" };
    setDraft(next);
    onApply(next);
  };
  const resetRoomTypes = () => {
    const next = { ...draft, roomTypeIds: [] };
    setDraft(next);
    onApply(next);
  };
  const resetLocations = () => {
    const next = { ...draft, locations: [] };
    setDraft(next);
    onApply(next);
  };

  const activeCount =
    (value.roomTypeIds?.length ?? 0) +
    (value.locations?.length ?? 0) +
    (value.priceMin ? 1 : 0) +
    (value.priceMax ? 1 : 0);

  const priceActive = !!(draft.priceMin || draft.priceMax);
  const priceRangeCheck = validatePriceRange(draft.priceMin, draft.priceMax);
  const priceRangeError = !priceRangeCheck.ok && priceActive ? priceRangeCheck : null;

  return (
    <div className="filter-bar">
      {/* Top row: live price inputs + filter toggle */}
      <div className="filter-bar__top">
        <div className="filter-bar__search">
          <span className="filter-bar__search-icon" aria-hidden="true">
            <Banknote size={16} strokeWidth={1.8} />
          </span>
          <div className="filter-bar__price-field">
            <input
              inputMode="numeric"
              className="filter-bar__price-input"
              placeholder={t("filter.price_min_short", "Min")}
              value={draft.priceMin ?? ""}
              onChange={(e) => setPrice("priceMin", e.target.value)}
              aria-label={t("filter.price_from", "Min price")}
            />
          </div>
          <span className="filter-bar__sep" aria-hidden="true" />
          <div className="filter-bar__price-field">
            <input
              inputMode="numeric"
              className="filter-bar__price-input"
              placeholder={t("filter.price_max_short", "Max")}
              value={draft.priceMax ?? ""}
              onChange={(e) => setPrice("priceMax", e.target.value)}
              aria-label={t("filter.price_to", "Max price")}
            />
          </div>
          <span className="filter-bar__currency" aria-hidden="true">
            {t("filter.currency_short", "UZS")}
          </span>
          {priceActive && (
            <button
              type="button"
              className="filter-bar__inline-reset"
              onClick={resetPrice}
              aria-label={t("filter.reset", "Reset")}
            >
              ×
            </button>
          )}
        </div>
        <button
          type="button"
          className={`filter-bar__toggle ${open ? "is-open" : ""}`}
          onClick={() => setOpen((s) => !s)}
          aria-expanded={open}
          aria-label={t("filter.toggle", "Filters")}
        >
          <SlidersHorizontal size={18} strokeWidth={1.8} />
          {activeCount > 0 ? (
            <span className="filter-bar__badge">{activeCount}</span>
          ) : null}
        </button>
      </div>

      {priceRangeError && (
        <small className="form-hint form-hint--error" style={{ display: "block", marginTop: 4 }}>
          {t(priceRangeError.messageKey, priceRangeError.code, priceRangeError.params)}
        </small>
      )}

      {/* Reveal: room-type + location cards */}
      {open && (
        <div className="filter-bar__reveal">
          {roomTypes.length > 0 && (
            <section className="filter-bar__card">
              <div className="filter-bar__card-head">
                <span className="filter-bar__card-icon" aria-hidden="true">
                  <BedDouble size={16} strokeWidth={1.8} />
                </span>
                <h4>{t("filter.room_type", "Room type")}</h4>
                {(draft.roomTypeIds?.length ?? 0) > 0 && (
                  <button
                    type="button"
                    className="filter-bar__card-reset"
                    onClick={resetRoomTypes}
                  >
                    {t("filter.reset", "Reset")}
                  </button>
                )}
              </div>
              <div className="filter-bar__chips">
                {roomTypes.map((rt) => {
                  const on = (draft.roomTypeIds ?? []).includes(rt.id);
                  return (
                    <button
                      key={rt.id}
                      type="button"
                      className={`chip ${on ? "chip--on" : ""}`}
                      onClick={() => toggle("roomTypeIds", rt.id)}
                    >
                      {rt.name}
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          {locations.some((l) => l.active) && (
            <section className="filter-bar__card">
              <div className="filter-bar__card-head">
                <span className="filter-bar__card-icon" aria-hidden="true">
                  <MapPin size={16} strokeWidth={1.8} />
                </span>
                <h4>{t("filter.location", "Location")}</h4>
                {(draft.locations?.length ?? 0) > 0 && (
                  <button
                    type="button"
                    className="filter-bar__card-reset"
                    onClick={resetLocations}
                  >
                    {t("filter.reset", "Reset")}
                  </button>
                )}
              </div>
              <div className="filter-bar__chips">
                {locations
                  .filter((l) => l.active)
                  .map((l) => {
                    const on = (draft.locations ?? []).includes(l.code);
                    return (
                      <button
                        key={l.code}
                        type="button"
                        className={`chip ${on ? "chip--on" : ""}`}
                        onClick={() => toggle("locations", l.code)}
                      >
                        {l.label}
                      </button>
                    );
                  })}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

export default FilterBar;

FilterBar.propTypes = {
  value: PropTypes.shape({
    priceMin: PropTypes.string,
    priceMax: PropTypes.string,
    roomTypeIds: PropTypes.arrayOf(PropTypes.number),
    locations: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
  onApply: PropTypes.func.isRequired,
};
