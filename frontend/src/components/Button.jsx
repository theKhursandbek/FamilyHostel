function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  type = "button",
  onClick,
  style: customStyle,
}) {
  const baseStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    border: "none",
    borderRadius: 4,
    cursor: disabled ? "not-allowed" : "pointer",
    fontWeight: 500,
    fontSize: size === "sm" ? 13 : 14,
    padding: size === "sm" ? "4px 10px" : "8px 16px",
    opacity: disabled ? 0.6 : 1,
    transition: "background 0.15s",
  };

  const variants = {
    primary: { background: "#1a73e8", color: "#fff" },
    secondary: { background: "#f1f3f4", color: "#333", border: "1px solid #dadce0" },
    danger: { background: "#dc2626", color: "#fff" },
    ghost: { background: "transparent", color: "#1a73e8" },
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={{ ...baseStyle, ...variants[variant], ...customStyle }}
    >
      {children}
    </button>
  );
}

export default Button;
