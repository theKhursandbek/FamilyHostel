import PropTypes from "prop-types";
import "./EmptyState.css";

/**
 * EmptyState — used when a list is empty or unavailable.
 */
export default function EmptyState({ icon = "📭", title, hint, action }) {
  return (
    <div className="ui-empty">
      <div className="ui-empty__icon" aria-hidden>{icon}</div>
      {title && <h3 className="ui-empty__title">{title}</h3>}
      {hint && <p className="ui-empty__hint">{hint}</p>}
      {action && <div className="ui-empty__action">{action}</div>}
    </div>
  );
}

EmptyState.propTypes = {
  icon: PropTypes.node,
  title: PropTypes.string,
  hint: PropTypes.string,
  action: PropTypes.node,
};

export function ErrorState({ message, onRetry, retryLabel = "Retry" }) {
  return (
    <div className="ui-error">
      <span className="ui-error__icon" aria-hidden>⚠️</span>
      <span className="ui-error__msg">{message}</span>
      {onRetry && (
        <button type="button" className="ui-error__retry" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

ErrorState.propTypes = {
  message: PropTypes.string.isRequired,
  onRetry: PropTypes.func,
  retryLabel: PropTypes.string,
};

export function Skeleton({ height = 60, width = "100%", radius = "var(--r-md)" }) {
  return (
    <div
      className="ui-skeleton"
      style={{ height, width, borderRadius: radius }}
      aria-hidden
    />
  );
}

Skeleton.propTypes = {
  height: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  width: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  radius: PropTypes.string,
};
