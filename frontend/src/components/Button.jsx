function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  type = "button",
  onClick,
  className = "",
  style,
}) {
  const classes = [
    "btn",
    `btn-${variant}`,
    size === "sm" ? "btn-sm" : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={classes}
      style={style}
    >
      {children}
    </button>
  );
}

export default Button;
