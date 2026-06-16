import PropTypes from "prop-types";
import "./Button.css";

/**
 * Button — design-token-driven, full-width by default for mobile.
 */
export default function Button({
  variant = "primary",
  size = "md",
  block = true,
  disabled = false,
  loading = false,
  type = "button",
  onClick,
  children,
  className = "",
  ...rest
}) {
  const cls = [
    "ui-btn",
    `ui-btn--${variant}`,
    `ui-btn--${size}`,
    block ? "ui-btn--block" : "",
    loading ? "is-loading" : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <button
      type={type}
      className={cls}
      disabled={disabled || loading}
      onClick={onClick}
      {...rest}
    >
      {loading ? <span className="ui-btn__spinner" aria-hidden /> : children}
    </button>
  );
}

Button.propTypes = {
  variant: PropTypes.oneOf(["primary", "secondary", "ghost", "danger"]),
  size: PropTypes.oneOf(["sm", "md", "lg"]),
  block: PropTypes.bool,
  disabled: PropTypes.bool,
  loading: PropTypes.bool,
  type: PropTypes.oneOf(["button", "submit", "reset"]),
  onClick: PropTypes.func,
  children: PropTypes.node,
  className: PropTypes.string,
};
