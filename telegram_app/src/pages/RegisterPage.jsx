import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { UserPlus, LogIn, CheckCircle2 } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { useTelegram } from "../context/TelegramContext";
import BackButton from "../components/BackButton";
import PasswordInput from "../components/PasswordInput";
import {
  validateName,
  validatePhone,
  validateDOB,
  validatePassport,
  validatePassword,
  validateMatch,
  formatPhoneInput,
} from "../utils/validators";

function _readNext(search) {
  const params = new URLSearchParams(search);
  const next = params.get("next");
  if (next) { try { return decodeURIComponent(next); } catch { return next; } }
  return "/me";
}

const MAX_DOB = (() => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 16);
  return d.toISOString().slice(0, 10);
})();

function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { isAuthenticated, user, register } = useAuth();
  const { isInsideTelegram, requestContact } = useTelegram();

  const next = useMemo(() => _readNext(location.search), [location.search]);

  const [firstName, setFirstName] = useState(user?.first_name || "");
  const [lastName, setLastName] = useState(user?.last_name || "");
  const [dob, setDob] = useState(user?.date_of_birth || "");
  const [passport, setPassport] = useState(user?.passport_number || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [phoneVerified, setPhoneVerified] = useState(false); // came from requestContact
  const [requestingContact, setRequestingContact] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [touched, setTouched] = useState({});
  const touch = (name) => setTouched((s) => ({ ...s, [name]: true }));
  const touchAll = () =>
    setTouched({
      firstName: true, lastName: true, dob: true,
      passport: true, phone: true, password: true, confirm: true,
    });

  useEffect(() => {
    if (isAuthenticated && !user?.is_new && user?.passport_number) {
      navigate(next, { replace: true });
    }
  }, [isAuthenticated, user, navigate, next]);

  const checks = {
    firstName: validateName(firstName),
    lastName: validateName(lastName),
    dob: validateDOB(dob),
    passport: validatePassport(passport),
    phone: validatePhone(phone),
    password: validatePassword(password),
    confirm: validateMatch(password, confirm),
  };
  const errOf = (name) => (touched[name] && !checks[name].ok ? checks[name] : null);
  const allOk = Object.values(checks).every((c) => c.ok);

  const handleSharePhone = async () => {
    setRequestingContact(true);
    setError(null);
    try {
      const result = await requestContact();
      if (result) {
        setPhone(result);
        setPhoneVerified(true);
        touch("phone");
      } else {
        setError("auth.share_phone_denied");
      }
    } finally {
      setRequestingContact(false);
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    touchAll();
    if (!allOk || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await register({
        first_name: checks.firstName.value,
        last_name: checks.lastName.value,
        date_of_birth: checks.dob.value,
        passport_number: checks.passport.value,
        phone: checks.phone.value,
        password: checks.password.value,
        confirm_password: checks.password.value,
        phone_from_telegram: phoneVerified,
      });
      navigate(next, { replace: true });
    } catch (err) {
      const data = err?.response?.data;
      const CODE_MAP = {
        phone_already_registered: "auth.err_phone_taken",
        passport_already_registered: "auth.err_passport_taken",
        passwords_do_not_match: "validation.passwords_dont_match",
      };
      const raw =
        data?.phone ??
        data?.passport_number ??
        data?.confirm_password ??
        data?.password ??
        data?.detail ??
        null;
      const val = Array.isArray(raw) ? raw[0] : raw;
      const i18nKey = typeof val === "string" ? CODE_MAP[val] : null;
      setError(i18nKey || "auth.register_failed");
    } finally {
      setSubmitting(false);
    }
  };

  const loginHref = `/login?next=${encodeURIComponent(next)}`;

  return (
    <section className="auth-page">
      <BackButton />
      <header className="auth-page__header">
        <h1>
          <UserPlus size={22} strokeWidth={1.8} style={{ verticalAlign: "-4px", marginRight: 6 }} />
          {t("auth.register")}
        </h1>
        <p className="muted">{t("auth.register_hint")}</p>
      </header>

      <form className="auth-form" onSubmit={onSubmit} noValidate>
        <label className="auth-form__field">
          <span>{t("auth.first_name")}</span>
          <input
            type="text"
            autoComplete="given-name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value.replaceAll(/\s+/g, "").slice(0, 20))}
            onBlur={() => touch("firstName")}
            aria-invalid={errOf("firstName") ? "true" : "false"}
            maxLength={20}
            required
          />
          {errOf("firstName") && (
            <small className="form-hint form-hint--error">
              {t(errOf("firstName").messageKey, errOf("firstName").params)}
            </small>
          )}
        </label>

        <label className="auth-form__field">
          <span>{t("auth.last_name")}</span>
          <input
            type="text"
            autoComplete="family-name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value.replaceAll(/\s+/g, "").slice(0, 20))}
            onBlur={() => touch("lastName")}
            aria-invalid={errOf("lastName") ? "true" : "false"}
            maxLength={20}
            required
          />
          {errOf("lastName") && (
            <small className="form-hint form-hint--error">
              {t(errOf("lastName").messageKey, errOf("lastName").params)}
            </small>
          )}
        </label>

        <label className="auth-form__field">
          <span>{t("auth.dob")}</span>
          <input
            type="date"
            max={MAX_DOB}
            value={dob}
            onChange={(e) => setDob(e.target.value)}
            onBlur={() => touch("dob")}
            aria-invalid={errOf("dob") ? "true" : "false"}
            required
          />
          {errOf("dob") && (
            <small className="form-hint form-hint--error">
              {t(errOf("dob").messageKey, errOf("dob").params)}
            </small>
          )}
        </label>

        <label className="auth-form__field">
          <span>{t("auth.passport")}</span>
          <input
            type="text"
            autoComplete="off"
            placeholder="AB1234567"
            value={passport}
            onChange={(e) => {
              let v = e.target.value.toUpperCase().replaceAll(/\s+/g, "");
              const letters = v.replaceAll(/[^A-Z]/g, "").slice(0, 2);
              const digits = v.slice(letters.length).replaceAll(/\D/g, "").slice(0, 7);
              setPassport(letters + digits);
            }}
            onBlur={() => touch("passport")}
            aria-invalid={errOf("passport") ? "true" : "false"}
            maxLength={9}
            required
          />
          {errOf("passport") && (
            <small className="form-hint form-hint--error">
              {t(errOf("passport").messageKey, errOf("passport").params)}
            </small>
          )}
        </label>

        {/* Phone field вЂ” requestContact() inside Telegram, manual input outside */}
        <div className="auth-form__field">
          <span>{t("auth.phone")}</span>
          {isInsideTelegram && !phoneVerified ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleSharePhone}
              disabled={requestingContact}
            >
              {requestingContact ? t("common.loading") : t("auth.share_phone")}
            </button>
          ) : phoneVerified ? (
            <div className="phone-verified">
              <CheckCircle2 size={16} strokeWidth={2} className="phone-verified__icon" />
              <span>{phone}</span>
              <button
                type="button"
                className="link-btn"
                onClick={() => { setPhone(""); setPhoneVerified(false); }}
              >
                {t("common.cancel")}
              </button>
            </div>
          ) : (
            <input
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              placeholder="+998901234567"
              value={phone}
              onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
              onFocus={() => { if (!phone) setPhone("+998"); }}
              onBlur={() => touch("phone")}
              aria-invalid={errOf("phone") ? "true" : "false"}
              maxLength={13}
              required
            />
          )}
          {!phoneVerified && errOf("phone") && (
            <small className="form-hint form-hint--error">
              {t(errOf("phone").messageKey, errOf("phone").params)}
            </small>
          )}
        </div>

        <label className="auth-form__field">
          <span>{t("auth.password")}</span>
          <PasswordInput
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value.replaceAll(/\s+/g, ""))}
            onBlur={() => touch("password")}
            aria-invalid={errOf("password") ? "true" : "false"}
            minLength={8}
          />
          {errOf("password") && (
            <small className="form-hint form-hint--error">
              {t(errOf("password").messageKey, errOf("password").params)}
            </small>
          )}
        </label>

        <label className="auth-form__field">
          <span>{t("auth.confirm_password")}</span>
          <PasswordInput
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value.replaceAll(/\s+/g, ""))}
            onBlur={() => touch("confirm")}
            aria-invalid={errOf("confirm") ? "true" : "false"}
            minLength={8}
          />
          {errOf("confirm") && (
            <small className="form-hint form-hint--error">
              {t(errOf("confirm").messageKey, errOf("confirm").params)}
            </small>
          )}
        </label>

        {error && <div className="form-error" role="alert">{t(error)}</div>}

        <button
          type="submit"
          className="btn btn-primary auth-form__submit"
          disabled={!allOk || submitting || (isInsideTelegram && !phoneVerified)}
        >
          <UserPlus size={16} strokeWidth={1.8} />
          {submitting ? t("common.loading") : t("auth.register_submit")}
        </button>
      </form>

      <div className="auth-page__alt">
        <p className="muted">{t("auth.have_account")}</p>
        <Link to={loginHref} className="btn btn-secondary">
          <LogIn size={16} strokeWidth={1.8} />
          {t("auth.login")}
        </Link>
      </div>

      <p style={{ height: "var(--bottom-nav-height)" }} aria-hidden />
    </section>
  );
}

export default RegisterPage;

