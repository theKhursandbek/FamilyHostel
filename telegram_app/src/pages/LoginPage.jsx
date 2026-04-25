import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTelegram } from "../context/TelegramContext";
import { ErrorBox, Loader } from "../components/Status";

const DEV_FALLBACK_ENABLED = import.meta.env.VITE_DEV_FALLBACK_LOGIN === "true";

/**
 * Sign-in screen.
 *
 * - Inside Telegram: AuthContext auto-logs the user in via initData on mount,
 *   so this page shows a brief loader and then redirects.
 * - In a regular browser (testing / demo): if VITE_DEV_FALLBACK_LOGIN is on,
 *   render a phone+password form so the staff/client UI can be exercised
 *   without a real bot. Otherwise show an explanatory message.
 */
function LoginPage() {
  const navigate = useNavigate();
  const { isInsideTelegram } = useTelegram();
  const { isAuthenticated, authBusy, authError, loginWithPhone } = useAuth();

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [submitError, setSubmitError] = useState("");

  if (isAuthenticated) {
    navigate("/me", { replace: true });
    return null;
  }

  if (isInsideTelegram && authBusy) return <Loader message="Signing you in…" />;

  if (isInsideTelegram && authError) {
    return <ErrorBox message={authError} />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError("");
    try {
      await loginWithPhone(phone, password);
    } catch (err) {
      setSubmitError(
        err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          "Sign-in failed."
      );
    }
  };

  if (!DEV_FALLBACK_ENABLED) {
    return (
      <div>
        <h1>Sign in</h1>
        <p className="text-hint">
          This Mini App authenticates automatically when opened from inside
          Telegram. Please open it via the FamilyHostel bot.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>Sign in</h1>
      <p className="text-hint" style={{ marginBottom: 16 }}>
        Demo mode — using your admin-panel phone &amp; password.
      </p>

      {(submitError || authError) && (
        <ErrorBox message={submitError || authError} />
      )}

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label className="label" htmlFor="phone">Phone</label>
          <input
            id="phone"
            className="input"
            type="tel"
            inputMode="tel"
            placeholder="+998..."
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <input
            id="password"
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button type="submit" className="btn" disabled={authBusy}>
          {authBusy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

export default LoginPage;
