import { useEffect } from "react";
import PropTypes from "prop-types";
import { useTelegram } from "../context/TelegramContext";

/**
 * ThemeProvider — pushes Telegram themeParams into CSS variables on `:root`
 * and toggles `html[data-tg-scheme="dark"]` so token overrides work.
 *
 * Re-runs whenever Telegram fires `themeChanged` so live theme switching
 * (user toggles dark mode in Telegram) is reflected immediately.
 */
export function ThemeProvider({ children }) {
  const { webApp } = useTelegram();

  useEffect(() => {
    const apply = () => {
      const tg = webApp || globalThis.Telegram?.WebApp;
      const params = tg?.themeParams || {};
      const root = document.documentElement;
      Object.entries(params).forEach(([k, v]) => {
        if (!v) return;
        // Telegram keys: bg_color → --tg-theme-bg-color
        const cssVar = `--tg-theme-${k.replaceAll("_", "-")}`;
        root.style.setProperty(cssVar, v);
      });
      const scheme = tg?.colorScheme;
      if (scheme === "dark" || scheme === "light") {
        root.setAttribute("data-tg-scheme", scheme);
      }
    };

    apply();

    const tg = webApp || globalThis.Telegram?.WebApp;
    if (!tg?.onEvent) return undefined;
    tg.onEvent("themeChanged", apply);
    return () => {
      try { tg.offEvent?.("themeChanged", apply); } catch { /* noop */ }
    };
  }, [webApp]);

  return children;
}

ThemeProvider.propTypes = { children: PropTypes.node.isRequired };
