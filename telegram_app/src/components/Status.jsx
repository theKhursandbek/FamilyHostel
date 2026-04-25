import PropTypes from "prop-types";

export function Loader({ message }) {
  return (
    <div className="center-spinner">
      <div className="spinner" aria-label={message || "Loading"} />
    </div>
  );
}
Loader.propTypes = { message: PropTypes.string };

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="error">
      <p style={{ margin: "0 0 8px" }}>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
ErrorBox.propTypes = { message: PropTypes.string.isRequired, onRetry: PropTypes.func };

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}
Empty.propTypes = { children: PropTypes.node };
