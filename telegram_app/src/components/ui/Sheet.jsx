import { useEffect } from "react";
import PropTypes from "prop-types";
import "./Sheet.css";

/**
 * Sheet — bottom sheet modal. Click backdrop or close button to dismiss.
 * Use for confirmation dialogs, action menus, or form popups.
 */
export default function Sheet({ open, title, onClose, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="ui-sheet" role="dialog" aria-modal="true">
      <div
        className="ui-sheet__backdrop"
        onClick={onClose}
        role="presentation"
      />
      <div className="ui-sheet__panel">
        {title && (
          <header className="ui-sheet__header">
            <h3>{title}</h3>
            <button
              type="button"
              className="ui-sheet__close"
              onClick={onClose}
              aria-label="Close"
            >
              ✕
            </button>
          </header>
        )}
        <div className="ui-sheet__body">{children}</div>
        {footer && <footer className="ui-sheet__footer">{footer}</footer>}
      </div>
    </div>
  );
}

Sheet.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  children: PropTypes.node,
  footer: PropTypes.node,
};
