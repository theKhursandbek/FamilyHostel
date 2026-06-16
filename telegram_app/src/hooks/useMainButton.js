import { useEffect } from "react";
import { useTelegram } from "../context/TelegramContext";

/**
 * Configure Telegram's bottom MainButton from any page.
 *
 * Usage:
 *   useMainButton({
 *     text: "Confirm",
 *     visible: dates.from && dates.to,
 *     loading: submitting,
 *     onClick: handleConfirm,
 *   });
 */
export default function useMainButton({
  text,
  visible = true,
  loading = false,
  disabled = false,
  onClick,
  color,
  textColor,
} = {}) {
  const { webApp } = useTelegram();

  useEffect(() => {
    const btn = webApp?.MainButton;
    if (!btn) return undefined;

    if (text) btn.setText(text);
    if (color || textColor) {
      btn.setParams({
        ...(color ? { color } : {}),
        ...(textColor ? { text_color: textColor } : {}),
      });
    }
    if (disabled || !visible) {
      btn.disable();
    } else {
      btn.enable();
    }
    if (loading) btn.showProgress?.(false); else btn.hideProgress?.();

    if (visible) btn.show(); else btn.hide();

    const handler = () => { if (!disabled && !loading) onClick?.(); };
    btn.onClick(handler);

    return () => {
      try {
        btn.offClick(handler);
        btn.hide();
        btn.hideProgress?.();
      } catch { /* ignore */ }
    };
  }, [webApp, text, visible, loading, disabled, onClick, color, textColor]);
}
