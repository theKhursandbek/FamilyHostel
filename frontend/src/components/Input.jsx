function Input({
  label,
  id,
  type = "text",
  value,
  onChange,
  placeholder,
  required = false,
  disabled = false,
  error,
  style: customStyle,
  ...rest
}) {
  return (
    <div style={{ marginBottom: 16, ...customStyle }}>
      {label && (
        <label
          htmlFor={id}
          style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 500 }}
        >
          {label}
          {required && <span style={{ color: "#dc2626" }}> *</span>}
        </label>
      )}
      <input
        id={id}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        style={{
          width: "100%",
          padding: 8,
          border: `1px solid ${error ? "#dc2626" : "#dadce0"}`,
          borderRadius: 4,
          fontSize: 14,
          outline: "none",
          boxSizing: "border-box",
        }}
        {...rest}
      />
      {error && (
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "#dc2626" }}>{error}</p>
      )}
    </div>
  );
}

export default Input;
