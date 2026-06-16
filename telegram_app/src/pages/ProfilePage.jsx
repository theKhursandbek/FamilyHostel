import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LogOut, Pencil } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { fmtDate } from "../utils/format";

/**
 * Profile / hub page — minimalistic.
 *
 * Avatar with initials → name + phone subtitle → details list →
 * navigation links (Bookings, Edit) → Sign out.
 */
export default function ProfilePage() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();

  const fullName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    t("profile.account", "Account");

  const rows = [
    { label: t("auth.dob", "Date of birth"), value: fmtDate(user?.date_of_birth, i18n.language) },
    { label: t("auth.passport", "Passport"), value: user?.passport_number || "—" },
    { label: t("auth.phone", "Phone"), value: user?.phone || "—" },
  ];

  return (
    <section className="profile-page">
      <header className="profile-hero">
        <h1 className="profile-hero__name">{fullName}</h1>
      </header>

      <ul className="profile-list">
        {rows.map(({ label, value }) => (
          <li key={label} className="profile-list__row">
            <span className="profile-list__label">{label}</span>
            <span className="profile-list__value">{value}</span>
          </li>
        ))}
      </ul>

      <div className="profile-edit-action-row">
        <Link to="/me/edit" className="profile-edit-action">
          <Pencil size={14} strokeWidth={1.8} />
          <span>{t("profile.edit", "Edit profile")}</span>
        </Link>
      </div>

      <button
        type="button"
        className="btn btn-secondary profile-page__logout"
        onClick={logout}
      >
        <LogOut size={16} strokeWidth={1.8} />
        {t("auth.logout", "Sign out")}
      </button>
    </section>
  );
}

