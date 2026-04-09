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
  className = "",
  ...rest
}) {
  return (
    <div className="form-group">
      {label && (
        <label htmlFor={id} className="label">
          {label}
          {required && <span className="text-accent"> *</span>}
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
        className={`input${error ? " error" : ""} ${className}`.trim()}
        {...rest}
      />
      {error && <p className="form-error">{error}</p>}
    </div>
  );
}

export default Input;
