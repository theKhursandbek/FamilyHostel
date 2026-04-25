import { useEffect } from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import { useTelegram } from "../context/TelegramContext";

/**
 * Wires the Telegram BackButton (top-left chevron in the WebApp header) to
 * `navigate(-1)` or a custom handler. Renders nothing.
 *
 * Outside Telegram it's a no-op (mobile browsers handle Back natively).
 */
function BackButton({ to, onClick }) {
  const { showBackButton, isInsideTelegram } = useTelegram();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isInsideTelegram) return undefined;
    const handler = () => {
      if (onClick) onClick();
      else if (to) navigate(to);
      else navigate(-1);
    };
    return showBackButton(handler);
  }, [isInsideTelegram, showBackButton, navigate, to, onClick]);

  return null;
}

BackButton.propTypes = {
  to: PropTypes.string,
  onClick: PropTypes.func,
};

export default BackButton;
