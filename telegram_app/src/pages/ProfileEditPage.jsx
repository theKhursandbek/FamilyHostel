import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { KeyRound } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { updateProfile } from "../services/auth";
import BackButton from "../components/BackButton";
import {
  validateName,
  validateDOB,
  validatePassport,
  maxDOBForAge,
} from "../utils/validators";

/**
 * Profile editor — first/last name, date of birth, phone, passport.
 *
 * POSTs to /auth/profile/, refreshes AuthContext, then returns to /me.
 */
export default function ProfileEditPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user, setUser } = useAuth();

  const [form, setForm] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    date_of_birth: user?.date_of_birth || "",
    passport_number: user?.passport_number || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [touched, setTouched] = useState({});
  const touch = (k) => setTouched((s) => ({ ...s, [k]: true }));

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  // DOB and passport are optional in the profile editor (the user may not
  // have set them yet); only validate if provided. First/last name are
  // required because the account always has them.
  const checks = {
    first_name: validateName(form.first_name),
    last_name: validateName(form.last_name),
    date_of_birth: form.date_of_birth ? validateDOB(form.date_of_birth) : { ok: true, value: null },
    passport_number: form.passport_number ? validatePassport(form.passport_number) : { ok: true, value: "" },
  };
  const errOf = (k) => (touched[k] && !checks[k].ok ? checks[k] : null);
  const allOk = Object.values(checks).every((c) => c.ok);

  const handleSave = async (e) => {
    e.preventDefault();
    setTouched({ first_name: true, last_name: true, date_of_birth: true, passport_number: true });
    if (saving || !allOk) return;
    setSaving(true);
    setError(null);
    try {
      const merged = await updateProfile({
        first_name: checks.first_name.value,
        last_name: checks.last_name.value,
        date_of_birth: checks.date_of_birth.value || null,
        passport_number: checks.passport_number.value || "",
      });
      if (setUser) setUser(merged);
      navigate("/me");
    } catch (err) {
      const detail = err?.response?.data?.detail
        || err?.response?.data
        || err?.message
        || t("common.error");
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="profile-edit">
      <BackButton />
      <header className="profile-edit__header">
        <h1>{t("profile.edit_title", "Edit profile")}</h1>
      </header>

      <form className="profile-edit__form" onSubmit={handleSave} noValidate>
        <div className="field-grid">
          <label className="field">
            <span>{t("auth.first_name", "First name")}</span>
            <input
              type="text"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value.replace(/\s+/g, "").slice(0, 20) })}
              onBlur={() => touch("first_name")}
              aria-invalid={errOf("first_name") ? "true" : "false"}
              autoComplete="given-name"
              maxLength={20}
              required
            />
            {errOf("first_name") && (
              <small className="form-hint form-hint--error">
                {t(errOf("first_name").messageKey, errOf("first_name").code, errOf("first_name").params)}
              </small>
            )}
          </label>
          <label className="field">
            <span>{t("auth.last_name", "Last name")}</span>
            <input
              type="text"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value.replace(/\s+/g, "").slice(0, 20) })}
              onBlur={() => touch("last_name")}
              aria-invalid={errOf("last_name") ? "true" : "false"}
              autoComplete="family-name"
              maxLength={20}
              required
            />
            {errOf("last_name") && (
              <small className="form-hint form-hint--error">
                {t(errOf("last_name").messageKey, errOf("last_name").code, errOf("last_name").params)}
              </small>
            )}
          </label>
        </div>

        <label className="field">
          <span>{t("auth.dob", "Date of birth")}</span>
          <input
            type="date"
            max={maxDOBForAge(16)}
            value={form.date_of_birth || ""}
            onChange={set("date_of_birth")}
            onBlur={() => touch("date_of_birth")}
            aria-invalid={errOf("date_of_birth") ? "true" : "false"}
          />
          {errOf("date_of_birth") && (
            <small className="form-hint form-hint--error">
              {t(errOf("date_of_birth").messageKey, errOf("date_of_birth").code, errOf("date_of_birth").params)}
            </small>
          )}
        </label>

        <label className="field">
          <span>{t("auth.passport", "Passport")}</span>
          <input
            type="text"
            value={form.passport_number}
            onChange={(e) => {
              let v = e.target.value.toUpperCase().replace(/\s+/g, "");
              const letters = v.replace(/[^A-Z]/g, "").slice(0, 2);
              const digits = v.slice(letters.length).replace(/\D/g, "").slice(0, 7);
              setForm({ ...form, passport_number: letters + digits });
            }}
            onBlur={() => touch("passport_number")}
            aria-invalid={errOf("passport_number") ? "true" : "false"}
            placeholder="AB1234567"
            autoComplete="off"
            maxLength={9}
          />
          {errOf("passport_number") && (
            <small className="form-hint form-hint--error">
              {t(errOf("passport_number").messageKey, errOf("passport_number").code, errOf("passport_number").params)}
            </small>
          )}
        </label>

        {error && <div className="form-error" role="alert">{error}</div>}

        <div className="profile-edit__actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(-1)}
            disabled={saving}
          >
            {t("common.cancel", "Cancel")}
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={saving || !allOk}
          >
            {saving ? t("common.loading", "…") : t("common.save", "Save")}
          </button>
        </div>

        <button
          type="button"
          className="btn btn-ghost profile-edit__change-pwd"
          onClick={() => navigate("/me/change-password")}
          style={{ width: "100%", marginTop: "var(--s-2)" }}
        >
          <KeyRound size={15} strokeWidth={1.8} style={{ verticalAlign: "-2px", marginRight: 5 }} />
          {t("auth.change_password")}
        </button>
      </form>
    </section>
  );
}
