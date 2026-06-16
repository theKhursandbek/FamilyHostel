import { useEffect } from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { useTelegram } from "../context/TelegramContext";

/**
 * Back navigation control.
 *
 *  • Wires the Telegram WebApp top-bar BackButton to the same handler so
 *    Telegram's native chevron always works (no-op outside Telegram).
 *  • Always renders a visible outlined chevron pill so the user has an
 *    accurate, reliable Back affordance on every subpage — both inside
 *    Telegram and in the browser.
 */
function BackButton({ to, onClick, label }) {
  const { showBackButton, isInsideTelegram } = useTelegram();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const go = () => {
    if (onClick) onClick();
    else if (to) navigate(to);
    else navigate(-1);
  };

  useEffect(() => {
    if (!isInsideTelegram) return undefined;
    return showBackButton(go);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInsideTelegram, showBackButton, to, onClick]);

  return (
    <button
      type="button"
      className="page-back"
      onClick={go}
      aria-label={t("common.back", "Back")}
    >
      <ArrowLeft size={16} strokeWidth={1.8} />
      <span>{label || t("common.back", "Back")}</span>
    </button>
  );
}

BackButton.propTypes = {
  to: PropTypes.string,
  onClick: PropTypes.func,
  label: PropTypes.string,
};

export default BackButton;
