import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import { useTelegram } from "./TelegramContext";
import * as authService from "../services/auth";

/**
 * Auth wrapper: derives the current user from localStorage on mount, and
 * — when running inside Telegram — performs a *one-shot* automatic login
 * with `initData` so the user never sees a sign-in screen.
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const { initData, isInsideTelegram } = useTelegram();
  const navigate = useNavigate();

  const [user, setUser] = useState(() => authService.getStoredUser());
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState(null);

  // -------------------------------------------------------------------
  // Auto-login from Telegram initData
  // -------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    if (!isInsideTelegram || !initData || authService.hasToken()) return;
    setAuthBusy(true);
    setAuthError(null);
    authService
      .loginWithTelegram(initData)
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((err) => {
        if (!cancelled) {
          setAuthError(
            err.response?.data?.error?.message ||
              err.response?.data?.detail ||
              "Telegram authentication failed."
          );
        }
      })
      .finally(() => !cancelled && setAuthBusy(false));
    return () => {
      cancelled = true;
    };
  }, [isInsideTelegram, initData]);

  // -------------------------------------------------------------------
  // Manual phone+password login (demo mode)
  // -------------------------------------------------------------------
  const loginWithPhone = useCallback(async (phone, password) => {
    setAuthBusy(true);
    setAuthError(null);
    try {
      const u = await authService.loginWithPhone(phone, password);
      setUser(u);
      navigate("/me");
      return u;
    } catch (err) {
      setAuthError(
        err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          "Invalid phone or password."
      );
      throw err;
    } finally {
      setAuthBusy(false);
    }
  }, [navigate]);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    navigate("/");
  }, [navigate]);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      authBusy,
      authError,
      loginWithPhone,
      logout,
    }),
    [user, authBusy, authError, loginWithPhone, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = { children: PropTypes.node.isRequired };

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
