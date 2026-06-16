import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { KeyRound } from "lucide-react";

import BackButton from "../../components/BackButton";
import PasswordInput from "../../components/PasswordInput";
import {
  validatePassword,
  validateMatch,
} from "../../utils/validators";
import { changePassword } from "../../services/auth";

/**
 * Change-password page (authenticated).
 * Requires current password for verification вЂ” no OTP needed.
 * Lives at /me/change-password (ProtectedRoute).
 */
export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");

  const [touched, setTouched] = useState({});
  const touch = (k) => setTouched((s) => ({ ...s, [k]: true }));
  const touchAll = () => setTouched({ currentPwd: true, newPwd: true, confirmPwd: true });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const pwdCheck = validatePassword(newPwd);
  const matchCheck = validateMatch(newPwd, confirmPwd);
  const currentOk = currentPwd.length >= 1;
  const formOk = currentOk && pwdCheck.ok && matchCheck.ok;

  const handleSubmit = async (e) => {
    e.preventDefault();
    touchAll();
    if (!formOk || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await changePassword({
        current_password: currentPwd,
        new_password: pwdCheck.value,
        confirm_password: pwdCheck.value,
      });
      navigate("/me");
    } catch (err) {
      const data = err?.response?.data;
      const code = data?.code || data?.detail;
      if (code === "current_password_wrong") {
        setError("auth.err_wrong_current_password");
      } else if (code === "passwords_do_not_match") {
        setError("validation.passwords_dont_match");
      } else {
        setError("common.error");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="auth-page">
      <BackButton />
      <header className="auth-page__header">
        <h1>
          <KeyRound size={22} strokeWidth={1.8} style={{ verticalAlign: "-4px", marginRight: 6 }} />
          {t("auth.change_password_title")}
        </h1>
        <p className="muted">{t("auth.change_password_hint")}</p>
      </header>

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label className="auth-form__field">
          <span>{t("auth.current_password")}</span>
          <PasswordInput
            value={currentPwd}
            onChange={(e) => setCurrentPwd(e.target.value.replaceAll(/\s/g, ""))}
            onBlur={() => touch("currentPwd")}
            autoComplete="current-password"
            aria-invalid={touched.currentPwd && !currentOk ? "true" : "false"}
          />
        </label>

        <label className="auth-form__field">
          <span>{t("auth.new_password")}</span>
          <PasswordInput
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value.replaceAll(/\s/g, ""))}
            onBlur={() => touch("newPwd")}
            autoComplete="new-password"
            aria-invalid={touched.newPwd && !pwdCheck.ok ? "true" : "false"}
            minLength={8}
          />
          {touched.newPwd && !pwdCheck.ok && (
            <small className="form-hint form-hint--error">
              {t(pwdCheck.messageKey, pwdCheck.params)}
            </small>
          )}
        </label>

        <label className="auth-form__field">
          <span>{t("auth.confirm_new_password")}</span>
          <PasswordInput
            value={confirmPwd}
            onChange={(e) => setConfirmPwd(e.target.value.replaceAll(/\s/g, ""))}
            onBlur={() => touch("confirmPwd")}
            autoComplete="new-password"
            aria-invalid={touched.confirmPwd && !matchCheck.ok ? "true" : "false"}
            minLength={8}
          />
          {touched.confirmPwd && !matchCheck.ok && (
            <small className="form-hint form-hint--error">
              {t(matchCheck.messageKey, matchCheck.params)}
            </small>
          )}
        </label>

        {error && <div className="form-error" role="alert">{t(error)}</div>}

        <button
          type="submit"
          className="btn btn-primary auth-form__submit"
          disabled={submitting}
        >
          {submitting ? t("common.loading") : t("auth.change_password")}
        </button>
      </form>
    </section>
  );
}

/**
 * Change-password page (authenticated).
 *
 * Step 1 вЂ” send OTP to Telegram.
 * Step 2 вЂ” enter OTP + new password + confirm в†’ save.
 *
 * Lives at /me/change-password (ProtectedRoute).
 */
