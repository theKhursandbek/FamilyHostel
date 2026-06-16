import { createContext, useContext, useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";

/**
 * Thin wrapper around `window.Telegram.WebApp`.
 *
 * - Exposes `webApp`, `initData`, `user`, `isInsideTelegram`.
 * - Calls `ready()` and `expand()` once on mount.
 * - Provides helpers to control the Telegram BackButton from any page.
 *
 * When the SDK is unavailable (regular browser) the context still mounts
 * with `isInsideTelegram=false` and no-op helpers, so the rest of the app
 * doesn't have to defensively check for `window.Telegram` everywhere.
 */
const TelegramContext = createContext(null);

export function TelegramProvider({ children }) {
  const [webApp, setWebApp] = useState(null);

  useEffect(() => {
    const tg = globalThis.Telegram?.WebApp;
    if (!tg) return;
    try {
      tg.ready();
      tg.expand();
    } catch {
      // Older host versions may throw — safe to ignore.
    }
    setWebApp(tg);
  }, []);

  const value = useMemo(() => {
    const initData = webApp?.initData || "";
    const tgUser = webApp?.initDataUnsafe?.user || null;
    const startParam = webApp?.initDataUnsafe?.start_param || "";
    return {
      webApp,
      initData,
      user: tgUser,
      startParam,
      isInsideTelegram: Boolean(webApp && initData),
      showBackButton(handler) {
        if (!webApp?.BackButton) return () => {};
        webApp.BackButton.show();
        webApp.BackButton.onClick(handler);
        return () => {
          webApp.BackButton.offClick(handler);
          webApp.BackButton.hide();
        };
      },
      hapticImpact(style = "light") {
        webApp?.HapticFeedback?.impactOccurred?.(style);
      },
      hapticNotification(type = "success") {
        webApp?.HapticFeedback?.notificationOccurred?.(type);
      },
      openInvoice(slug) {
        return new Promise((resolve) => {
          if (!webApp?.openInvoice) {
            resolve("unsupported");
            return;
          }
          try {
            webApp.openInvoice(slug, (status) => resolve(status));
          } catch {
            resolve("failed");
          }
        });
      },
      requestContact() {
        return new Promise((resolve) => {
          if (!webApp?.requestContact) { resolve(null); return; }
          try {
            webApp.requestContact((granted, response) => {
              if (!granted || !response?.contact?.phone_number) { resolve(null); return; }
              // Telegram gives "998901234567" or "+998901234567" — normalise to +
              const raw = response.contact.phone_number;
              resolve(raw.startsWith("+") ? raw : "+" + raw);
            });
          } catch {
            resolve(null);
          }
        });
      },
    };
  }, [webApp]);

  return (
    <TelegramContext.Provider value={value}>
      {children}
    </TelegramContext.Provider>
  );
}

TelegramProvider.propTypes = { children: PropTypes.node.isRequired };

export function useTelegram() {
  const ctx = useContext(TelegramContext);
  if (!ctx) throw new Error("useTelegram must be used within TelegramProvider");
  return ctx;
}
