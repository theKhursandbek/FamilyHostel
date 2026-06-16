import PropTypes from "prop-types";
import "./Card.css";

export default function Card({ children, padded = true, className = "", onClick, ...rest }) {
  const cls = [
    "ui-card",
    padded ? "ui-card--padded" : "",
    onClick ? "ui-card--interactive" : "",
    className,
  ].filter(Boolean).join(" ");
  return (
    <div className={cls} onClick={onClick} {...rest}>
      {children}
    </div>
  );
}

Card.propTypes = {
  children: PropTypes.node,
  padded: PropTypes.bool,
  className: PropTypes.string,
  onClick: PropTypes.func,
};
