import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { KeyRound } from "lucide-react";

import BackButton from "../components/BackButton";
import PasswordInput from "../components/PasswordInput";
import {
  validatePhone,
  validatePassword,
  validateMatch,
  validateOtpCode,
  formatPhoneInput,
} from "../utils/validators";
import { sendTelegramOtp, resetPassword } from "../services/auth";
import { useAuth } from "../context/AuthContext";

const OTP_ERROR_MAP = {
  otp_expired: "auth.err_otp_expired",
  otp_invalid: "auth.err_otp_invalid",
  otp_max_attempts: "auth.err_otp_max_attempts",
  no_telegram: "auth.no_telegram",
  throttled: "auth.otp_throttled",
};
function _mapOtpError(code) {
  return OTP_ERROR_MAP[code] || null;
}

/**
 * Forgot-password flow (unauthenticated).
 *
 * Step 1 — enter phone → send OTP via Telegram.
 * Step 2 — enter OTP + new password + confirm → reset + auto-login.
 */
export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { setUser } = useAuth();

  const [step, setStep] = useState(1);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");

  const [touched, setTouched] = useState({});
  const touch = (k) => setTouched((s) => ({ ...s, [k]: true }));
  const touchAll = (...keys) =>
    setTouched((s) => keys.reduce((acc, k) => ({ ...acc, [k]: true }), s));

  const [sending, setSending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [countdown, setCountdown] = useState(0);

  const phoneCheck = validatePhone(phone);
  const otpCheck = validateOtpCode(otp);
  const pwdCheck = validatePassword(newPwd);
  const matchCheck = validateMatch(newPwd, confirmPwd);

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0) return;
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [countdown]);

  const handleSendCode = async () => {
    touch("phone");
    if (!phoneCheck.ok || sending) return;
    setSending(true);
    setError(null);
    try {
      await sendTelegramOtp({ purpose: "forgot_password", phone: phoneCheck.value });
      setStep(2);
      setCountdown(60);
    } catch (err) {
      const data = err?.response?.data;
      if (data?.code === "no_telegram") {
        setError("auth.no_telegram");
      } else {
        setError(_mapOtpError(data?.code) || "common.error");
      }
    } finally {
      setSending(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0 || sending) return;
    setSending(true);
    setError(null);
    try {
      await sendTelegramOtp({ purpose: "forgot_password", phone: phoneCheck.value });
      setCountdown(60);
    } catch (err) {
      setError(_mapOtpError(err?.response?.data?.code) || "common.error");
    } finally {
      setSending(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    touchAll("otp", "newPwd", "confirmPwd");
    if (!otpCheck.ok || !pwdCheck.ok || !matchCheck.ok || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await resetPassword({
        phone: phoneCheck.value,
        code: otpCheck.value,
        new_password: pwdCheck.value,
        confirm_password: pwdCheck.value,
      });
      // Auto-login: tokens already stored by resetPassword in auth.js
      if (result.access && setUser) {
        // Refresh user from stored data
        const { getStoredUser } = await import("../services/auth");
        const u = getStoredUser();
        if (u) setUser(u);
      }
      navigate("/me", { replace: true });
    } catch (err) {
      setError(_mapOtpError(err?.response?.data?.detail || err?.response?.data?.code) || "common.error");
    } finally {
      setSubmitting(false);
    }
  };

  // -------------------------------------------------------------------------
  // Step 1: phone input
  // -------------------------------------------------------------------------
  if (step === 1) {
    return (
      <section className="auth-page">
        <BackButton />
        <header className="auth-page__header">
          <h1>
            <KeyRound size={22} strokeWidth={1.8} style={{ verticalAlign: "-4px", marginRight: 6 }} />
            {t("auth.forgot_title")}
          </h1>
          <p className="muted">{t("auth.forgot_hint")}</p>
        </header>

        <div className="auth-form">
          <label className="auth-form__field">
            <span>{t("auth.phone")}</span>
            <input
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              placeholder="+998901234567"
              value={phone}
              onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
              onFocus={() => { if (!phone) setPhone("+998"); }}
              onBlur={() => touch("phone")}
              aria-invalid={touched.phone && !phoneCheck.ok ? "true" : "false"}
              maxLength={13}
            />
            {touched.phone && !phoneCheck.ok && (
              <small className="form-hint form-hint--error">
                {t(phoneCheck.messageKey, phoneCheck.code, phoneCheck.params)}
              </small>
            )}
          </label>

          {error && <div className="form-error" role="alert">{t(error)}</div>}

          <button
            type="button"
            className="btn btn-primary auth-form__submit"
            onClick={handleSendCode}
            disabled={sending}
          >
            {sending ? t("common.loading") : t("auth.forgot_send")}
          </button>
        </div>

        <div className="auth-page__alt">
          <a href="/login" className="muted" style={{ fontSize: "var(--font-sm)" }}>
            {t("auth.have_account")} {t("auth.login")}
          </a>
        </div>
      </section>
    );
  }

  // -------------------------------------------------------------------------
  // Step 2: OTP + new passwords
  // -------------------------------------------------------------------------
  return (
    <section className="auth-page">
      <BackButton />
      <header className="auth-page__header">
        <h1>
          <KeyRound size={22} strokeWidth={1.8} style={{ verticalAlign: "-4px", marginRight: 6 }} />
          {t("auth.forgot_title")}
        </h1>
        <p className="muted">{t("auth.otp_sent_to")}</p>
      </header>

      <form className="auth-form" onSubmit={handleReset} noValidate>
        {/* OTP field */}
        <label className="auth-form__field">
          <span>{t("auth.otp_label")}</span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            maxLength={6}
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
            onBlur={() => touch("otp")}
            aria-invalid={touched.otp && !otpCheck.ok ? "true" : "false"}
            className="otp-input"
          />
          {touched.otp && !otpCheck.ok && (
            <small className="form-hint form-hint--error">
              {t(otpCheck.messageKey, otpCheck.code, otpCheck.params)}
            </small>
          )}
          <div className="otp-step__resend">
            {countdown > 0 ? (
              <span className="muted" style={{ fontSize: "var(--font-sm)" }}>
                {t("auth.otp_resend_in", { sec: countdown })}
              </span>
            ) : (
              <button type="button" className="link-btn" onClick={handleResend} disabled={sending}>
                {t("auth.otp_resend")}
              </button>
            )}
          </div>
        </label>

        {/* New password */}
        <label className="auth-form__field">
          <span>{t("auth.new_password")}</span>
          <PasswordInput
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value.replace(/\s/g, ""))}
            onBlur={() => touch("newPwd")}
            autoComplete="new-password"
            aria-invalid={touched.newPwd && !pwdCheck.ok ? "true" : "false"}
            minLength={8}
          />
          {touched.newPwd && !pwdCheck.ok && (
            <small className="form-hint form-hint--error">
              {t(pwdCheck.messageKey, pwdCheck.code, pwdCheck.params)}
            </small>
          )}
        </label>

        {/* Confirm */}
        <label className="auth-form__field">
          <span>{t("auth.confirm_new_password")}</span>
          <PasswordInput
            value={confirmPwd}
            onChange={(e) => setConfirmPwd(e.target.value.replace(/\s/g, ""))}
            onBlur={() => touch("confirmPwd")}
            autoComplete="new-password"
            aria-invalid={touched.confirmPwd && !matchCheck.ok ? "true" : "false"}
            minLength={8}
          />
          {touched.confirmPwd && !matchCheck.ok && (
            <small className="form-hint form-hint--error">
              {t(matchCheck.messageKey, matchCheck.code, matchCheck.params)}
            </small>
          )}
        </label>

        {error && <div className="form-error" role="alert">{t(error)}</div>}

        <button
          type="submit"
          className="btn btn-primary auth-form__submit"
          disabled={submitting}
        >
          {submitting ? t("common.loading") : t("auth.reset_submit")}
        </button>
      </form>
    </section>
  );
}
