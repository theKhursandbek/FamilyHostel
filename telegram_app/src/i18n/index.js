import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import ru from "./ru.json";
import uz from "./uz.json";

/**
 * i18n bootstrap (TELEGRAM_MINI_APP_PLAN.md D9).
 *
 * - Default locale: uz (Uzbek). Fallback chain: uz → ru → en.
 * - Detects language from `?lang=`, then localStorage (`tg_lang`), then
 *   navigator settings.
 * - When opened inside Telegram we override the detector with
 *   `tg.initDataUnsafe.user.language_code` (handled in `bootLanguage`).
 */
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      ru: { translation: ru },
      uz: { translation: uz },
    },
    lng: "uz",
    fallbackLng: ["uz", "ru", "en"],
    supportedLngs: ["uz", "ru", "en"],
    interpolation: { escapeValue: false },
    detection: {
      order: ["querystring", "localStorage", "navigator"],
      lookupQuerystring: "lang",
      lookupLocalStorage: "tg_lang",
      caches: ["localStorage"],
    },
  });

/**
 * Override the auto-detected language from Telegram on boot.
 * Maps unknown locales to UZ (e.g. "uz-cyrl" → "uz", "kk" → "ru").
 */
export function bootLanguage(tgLanguageCode) {
  if (!tgLanguageCode) return;
  const code = tgLanguageCode.toLowerCase().split(/[-_]/)[0];
  const map = { en: "en", ru: "ru", uz: "uz", kk: "ru", ky: "ru", tg: "ru", be: "ru" };
  const target = map[code] || "uz";
  if (i18n.language !== target) i18n.changeLanguage(target);
}

/**
 * Persist a manual language choice and switch immediately.
 * Used by the LanguageSwitcher control on the Profile page.
 */
export function setLanguage(lang) {
  if (!["uz", "ru", "en"].includes(lang)) return;
  try { localStorage.setItem("tg_lang", lang); } catch { /* private mode */ }
  if (i18n.language !== lang) i18n.changeLanguage(lang);
}

export const SUPPORTED_LANGUAGES = [
  { code: "uz", label: "O‘zbekcha" },
  { code: "ru", label: "Русский" },
  { code: "en", label: "English" },
];

export default i18n;
