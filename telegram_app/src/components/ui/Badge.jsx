import PropTypes from "prop-types";
import "./Badge.css";

const VARIANTS = ["success", "warning", "danger", "info", "muted"];

export default function Badge({ variant = "muted", children, className = "" }) {
  const v = VARIANTS.includes(variant) ? variant : "muted";
  return (
    <span className={`ui-badge ui-badge--${v} ${className}`}>{children}</span>
  );
}

Badge.propTypes = {
  variant: PropTypes.oneOf(VARIANTS),
  children: PropTypes.node,
  className: PropTypes.string,
};
