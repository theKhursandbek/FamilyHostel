import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LogIn, UserPlus } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { useTelegram } from "../context/TelegramContext";
import { Loader } from "../components/Status";
import BackButton from "../components/BackButton";
import PasswordInput from "../components/PasswordInput";
import { validatePhone, validateLoginPassword, formatPhoneInput } from "../utils/validators";

/**
 * Phone + password login.
 *
 * Reads ``?next=<encoded-url>`` (or location.state.from) and redirects there
 * on success. Falls back to ``/me``. Inside Telegram, AuthContext may
 * already auto-login via initData; we just spinner-wait in that case.
 */
function _readNext(search, state) {
  const params = new URLSearchParams(search);
  const next = params.get("next");
  if (next) {
    try { return decodeURIComponent(next); } catch { return next; }
  }
  return state?.from || "/me";
}

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { isInsideTelegram } = useTelegram();
  const { isAuthenticated, authBusy, loginWithPassword } = useAuth();

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ phone: false, password: false });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const next = _readNext(location.search, location.state);

  useEffect(() => {
    if (isAuthenticated) navigate(next, { replace: true });
  }, [isAuthenticated, navigate, next]);

  if (isAuthenticated) return null;
  if (isInsideTelegram && authBusy) {
    return <Loader message={t("auth.signing_in", "Signing you in…")} />;
  }

  const phoneCheck = validatePhone(phone);
  const passwordCheck = validateLoginPassword(password);
  const phoneError = touched.phone && !phoneCheck.ok ? phoneCheck : null;
  const passwordError = touched.password && !passwordCheck.ok ? passwordCheck : null;
  const canSubmit = phoneCheck.ok && passwordCheck.ok && !submitting;

  const onSubmit = async (e) => {
    e.preventDefault();
    setTouched({ phone: true, password: true });
    if (!phoneCheck.ok || !passwordCheck.ok || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await loginWithPassword({ phone: phoneCheck.value, password: passwordCheck.value });
      // useEffect above will redirect once `user` is set.
    } catch (err) {
      const data = err?.response?.data;
      const raw = data?.detail || data?.non_field_errors?.[0] || null;
      // Backend returns "Invalid credentials." or "Account is deactivated."
      // Store i18n key — translated at render so language switches apply live.
      if (raw?.toLowerCase().includes("deactivat")) {
        setError("auth.err_account_disabled");
      } else {
        setError("auth.login_failed");
      }
      setSubmitting(false);
    }
  };

  const registerHref = `/register?next=${encodeURIComponent(next)}`;

  return (
    <section className="auth-page">
      <BackButton to="/" />
      <header className="auth-page__header">
        <h1>{t("auth.login", "Sign in")}</h1>
        <p className="muted">
          {t("auth.login_hint", "Enter your phone and password to continue.")}
        </p>
      </header>

      <form className="auth-form" onSubmit={onSubmit} noValidate>
        <label className="auth-form__field">
          <span>{t("auth.phone", "Phone number")}</span>
          <input
            type="tel"
            inputMode="numeric"
            autoComplete="tel"
            placeholder="+998901234567"
            value={phone}
            onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
            onFocus={() => { if (!phone) setPhone("+998"); }}
            onBlur={() => setTouched((s) => ({ ...s, phone: true }))}
            aria-invalid={phoneError ? "true" : "false"}
            maxLength={13}
            required
          />
          {phoneError && (
            <small className="form-hint form-hint--error">
              {t(phoneError.messageKey, phoneError.code, phoneError.params)}
            </small>
          )}
        </label>

        <label className="auth-form__field">
          <span>{t("auth.password", "Password")}</span>
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value.replace(/\s+/g, ""))}
            onBlur={() => setTouched((s) => ({ ...s, password: true }))}
            autoComplete="current-password"
            aria-invalid={passwordError ? "true" : "false"}
          />
          {passwordError && (
            <small className="form-hint form-hint--error">
              {t(passwordError.messageKey, passwordError.code, passwordError.params)}
            </small>
          )}
        </label>

        <div className="auth-form__forgot">
          <Link
            to={`/forgot-password?next=${encodeURIComponent(next)}`}
            className="link-btn"
            tabIndex={0}
          >
            {t("auth.forgot_password")}
          </Link>
        </div>

        {error && <div className="form-error" role="alert">{t(error)}</div>}

        <button
          type="submit"
          className="btn btn-primary auth-form__submit"
          disabled={!canSubmit}
        >
          <LogIn size={16} strokeWidth={1.8} />
          {submitting
            ? t("common.loading", "…")
            : t("auth.login", "Sign in")}
        </button>
      </form>

      <div className="auth-page__alt">
        <p className="muted">{t("auth.no_account", "Don't have an account?")}</p>
        <Link to={registerHref} className="btn btn-secondary">
          <UserPlus size={16} strokeWidth={1.8} />
          {t("auth.register", "Register")}
        </Link>
      </div>
    </section>
  );
}

export default LoginPage;

