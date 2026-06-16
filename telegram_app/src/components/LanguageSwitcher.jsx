import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES, setLanguage } from "../i18n";

/**
 * Compact 3-pill language switcher used on the Profile page.
 *
 * Persists the choice in `localStorage.tg_lang` and updates i18next
 * immediately. Server-side language preference (Account.language) is
 * synced separately by the Profile screen via PATCH /auth/profile/.
 */
function LanguageSwitcher({ onChange }) {
  const { i18n } = useTranslation();
  const current = (i18n.resolvedLanguage || i18n.language || "uz").split("-")[0];

  return (
    <div
      className="lang-switcher"
      role="radiogroup"
      aria-label="Language"
      style={{ display: "flex", gap: 6, marginTop: 12 }}
    >
      {SUPPORTED_LANGUAGES.map(({ code, label }) => {
        const active = code === current;
        return (
          <button
            key={code}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => {
              setLanguage(code);
              onChange?.(code);
            }}
            className={active ? "btn btn-primary" : "btn btn-secondary"}
            style={{ flex: 1, padding: "8px 4px", fontSize: 13 }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default LanguageSwitcher;
