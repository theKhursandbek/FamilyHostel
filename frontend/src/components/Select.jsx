import { useEffect, useId, useRef, useState, useCallback } from "react";
import PropTypes from "prop-types";
import { ChevronDown, Check } from "lucide-react";

/**
 * Fully custom themed Select (combobox / listbox).
 *
 * Replaces native <select> so the dropdown popup is rendered by React
 * and styled by our CSS — not by the OS — eliminating the bright-blue
 * default highlight on Chrome/Edge.
 *
 * Props mirror the most common needs of native <select>:
 *   value       — currently selected option value (string|number|"")
 *   onChange    — called with the new value when user picks an option
 *   options     — array of { value, label, disabled? }
 *   placeholder — shown when no value is selected (e.g. "Select staff")
 *   disabled    — disables the whole control
 *   loading     — shows "Loading…" placeholder & disables interaction
 *   error       — when truthy, shows the error border (matches .select.error)
 *   id          — id for the trigger button (label htmlFor)
 *   className   — extra classes appended to .select-trigger
 *   emptyText   — text when there are no options (default "No options available")
 */
function Select({
  value,
  onChange,
  options,
  placeholder = "Select…",
  disabled = false,
  loading = false,
  error = false,
  id,
  className = "",
  emptyText = "No options available",
}) {
  const reactId = useId();
  const triggerId = id || `select-${reactId}`;
  const listboxId = `${triggerId}-listbox`;

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef(null);
  const triggerRef = useRef(null);
  const listRef = useRef(null);

  const isDisabled = disabled || loading;

  const valueStr = value === null || value === undefined ? "" : String(value);
  const selected = options.find((o) => String(o.value) === valueStr);
  const triggerLabel = loading
    ? "Loading…"
    : selected?.label ?? placeholder;

  const closeMenu = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
  }, []);

  const openMenu = useCallback(() => {
    if (isDisabled || options.length === 0) return;
    setOpen(true);
    const idx = options.findIndex((o) => String(o.value) === valueStr);
    setActiveIndex(Math.max(0, idx));
  }, [isDisabled, options, valueStr]);

  // Click outside / Esc to close
  useEffect(() => {
    if (!open) return undefined;
    const onDocMouse = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        closeMenu();
      }
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        closeMenu();
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDocMouse);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouse);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, closeMenu]);

  // Scroll active option into view
  useEffect(() => {
    if (!open || activeIndex < 0 || !listRef.current) return;
    const el = listRef.current.children[activeIndex];
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [open, activeIndex]);

  const commitOption = (opt) => {
    if (!opt || opt.disabled) return;
    onChange(opt.value);
    closeMenu();
    triggerRef.current?.focus();
  };

  const onTriggerKeyDown = (e) => {
    if (isDisabled) return;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        openMenu();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(options.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveIndex(options.length - 1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      commitOption(options[activeIndex]);
    } else if (e.key === "Tab") {
      closeMenu();
    }
  };

  const isPlaceholder = !selected && !loading;

  const triggerClasses = [
    "select-trigger",
    open ? "open" : "",
    error ? "error" : "",
    isPlaceholder ? "placeholder" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="select-wrapper" ref={wrapperRef}>
      <button
        type="button"
        id={triggerId}
        ref={triggerRef}
        className={triggerClasses}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={onTriggerKeyDown}
        disabled={isDisabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
      >
        <span className="select-trigger-label">{triggerLabel}</span>
        <ChevronDown
          size={14}
          strokeWidth={1.8}
          className={`select-trigger-icon${open ? " open" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        // a11y handled manually: keyboard nav lives on the trigger button.
        <div className="select-popup">
          {options.length === 0 ? (
            <div className="select-empty">{emptyText}</div>
          ) : (
            <ul
              id={listboxId}
              ref={listRef}
              role="listbox"
              tabIndex={-1}
              className="select-list"
              aria-activedescendant={
                activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined
              }
            >
              {options.map((opt, idx) => {
                const isSelected = String(opt.value) === valueStr;
                const isActive = idx === activeIndex;
                const optClasses = [
                  "select-option",
                  isSelected ? "selected" : "",
                  isActive ? "active" : "",
                  opt.disabled ? "disabled" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  // a11y: keyboard handling delegated to the parent listbox/trigger.
                  <li
                    id={`${listboxId}-opt-${idx}`}
                    key={`${opt.value}-${idx}`}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={opt.disabled || undefined}
                    className={optClasses}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onMouseDown={(e) => {
                      // Prevent the trigger from losing focus before click commits
                      e.preventDefault();
                    }}
                    onClick={() => commitOption(opt)}
                  >
                    <span className="select-option-label">{opt.label}</span>
                    {isSelected && (
                      <Check
                        size={14}
                        strokeWidth={2}
                        className="select-option-check"
                        aria-hidden="true"
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

Select.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      label: PropTypes.node.isRequired,
      disabled: PropTypes.bool,
    })
  ).isRequired,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  loading: PropTypes.bool,
  error: PropTypes.bool,
  id: PropTypes.string,
  className: PropTypes.string,
  emptyText: PropTypes.string,
};

export default Select;
