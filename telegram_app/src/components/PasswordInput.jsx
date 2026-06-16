import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * Password input with show/hide toggle.
 *
 * Drop-in replacement for `<input type="password">` inside an
 * `.auth-form__field` label. The containing `.pwd-wrap` div provides
 * position:relative so the toggle button overlays the right edge of the input.
 */
export default function PasswordInput({
  value,
  onChange,
  onBlur,
  autoComplete = "current-password",
  placeholder,
  "aria-invalid": ariaInvalid,
  ...rest
}) {
  const [show, setShow] = useState(false);

  return (
    <div className="pwd-wrap">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        autoComplete={autoComplete}
        placeholder={placeholder}
        aria-invalid={ariaInvalid}
        {...rest}
      />
      <button
        type="button"
        className="pwd-wrap__toggle"
        onClick={() => setShow((s) => !s)}
        tabIndex={-1}
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show
          ? <EyeOff size={16} strokeWidth={1.8} />
          : <Eye size={16} strokeWidth={1.8} />}
      </button>
    </div>
  );
}
