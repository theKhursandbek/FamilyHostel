import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Home, CalendarDays, User, Globe } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { SUPPORTED_LANGUAGES, setLanguage } from "../i18n";
import { completeProfile } from "../services/auth";

/**
 * Bottom navigation — floating glass pill.
 *
 * Tabs:
 *   - Browse  (always visible)
 *   - My Bookings (signed-in clients OR guests with a remembered phone)
 *   - Profile (always visible)
 *   - Language switcher — single button that cycles through SUPPORTED_LANGUAGES
 *     on each tap (no dropdown).
 */
function BottomNav() {
  const { t, i18n } = useTranslation();
  const { isAuthenticated } = useAuth();

  const current = (i18n.resolvedLanguage || i18n.language || "uz").split("-")[0];

  const cycleLang = () => {
    const codes = SUPPORTED_LANGUAGES.map((l) => l.code);
    const idx = codes.indexOf(current);
    const next = codes[(idx + 1) % codes.length] ?? codes[0];
    setLanguage(next);
    if (isAuthenticated) {
      completeProfile({ language: next }).catch(() => { /* best-effort */ });
    }
  };

  return (
    <nav className="bottom-nav" aria-label="Primary">
      <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="nav-icon"><Home size={24} strokeWidth={1.8} /></span>
        <span className="nav-label">{t("nav.home", "Browse")}</span>
      </NavLink>

      <NavLink to="/me/bookings" className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="nav-icon"><CalendarDays size={24} strokeWidth={1.8} /></span>
        <span className="nav-label">{t("nav.bookings", "Bookings")}</span>
      </NavLink>

      <NavLink to="/me" end className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="nav-icon"><User size={24} strokeWidth={1.8} /></span>
        <span className="nav-label">{t("nav.profile", "Profile")}</span>
      </NavLink>

      <button
        type="button"
        className="bottom-nav__lang-btn"
        aria-label={t("auth.language", "Language")}
        title={t("auth.language", "Language")}
        onClick={cycleLang}
      >
        <Globe size={20} strokeWidth={1.8} />
        {current.toUpperCase()}
      </button>
    </nav>
  );
}

export default BottomNav;
