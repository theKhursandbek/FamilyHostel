import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import { useTelegram } from "./TelegramContext";
import * as authService from "../services/auth";
import { bootLanguage } from "../i18n";

/**
 * Auth wrapper: derives the current user from localStorage on mount, and
 * — when running inside Telegram — performs a *one-shot* automatic login
 * with `initData` so the user never sees a sign-in screen.
 *
 * Side-effects on user state changes:
 *   - Opens / refreshes the role-appropriate WebSocket.
 *   - Routes brand-new clients to /onboarding to capture full_name + phone.
 *   - Boots the i18n language from Telegram's `language_code`.
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const { initData, isInsideTelegram, user: tgUser } = useTelegram();
  const navigate = useNavigate();

  const [user, setUser] = useState(() => authService.getStoredUser());
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState(null);

  // Boot the locale from Telegram on mount.
  useEffect(() => {
    if (tgUser?.language_code) bootLanguage(tgUser.language_code);
  }, [tgUser]);

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
        if (cancelled) return;
        setUser(u);
        // No forced redirect — new users land on home and are prompted
        // to register only when they try to access a protected page.
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
  }, [isInsideTelegram, initData, navigate]);

  const completeProfile = useCallback(async (payload) => {
    const updated = await authService.completeProfile(payload);
    setUser(updated);
    return updated;
  }, []);

  const register = useCallback(async (payload) => {
    setAuthError(null);
    const u = await authService.register(payload);
    setUser(u);
    return u;
  }, []);

  const loginWithPassword = useCallback(async (payload) => {
    setAuthError(null);
    const u = await authService.loginWithPassword(payload);
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    navigate("/");
  }, [navigate]);

  const value = useMemo(
    () => ({
      user,
      setUser,
      isAuthenticated: Boolean(user),
      authBusy,
      authError,
      completeProfile,
      register,
      loginWithPassword,
      logout,
      hasRole: (role) => Boolean(user?.roles?.includes(role)),
    }),
    [user, authBusy, authError, completeProfile, register, loginWithPassword, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = { children: PropTypes.node.isRequired };

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
