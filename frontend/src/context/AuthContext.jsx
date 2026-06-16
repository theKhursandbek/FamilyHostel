import { createContext, useContext, useState, useCallback, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import * as authService from "../services/auth";
import { getAccount } from "../services/accountsService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [isAuthenticated, setIsAuthenticated] = useState(() => authService.hasToken());
  const navigate = useNavigate();

  // Sync state if token exists on mount
  useEffect(() => {
    const storedUser = authService.getStoredUser();
    const hasToken = authService.hasToken();
    // If the stored user object predates the full_name patch, force a
    // re-login so we pick up the new fields (full_name, branch_name, ...).
    if (storedUser && !("full_name" in storedUser)) {
      authService.logout();
      setUser(null);
      setIsAuthenticated(false);
      return;
    }
    // Self-heal: strip obsolete brand prefixes from any cached
    // branch_name so stale localStorage doesn't leak the old name.
    if (storedUser?.branch_name) {
      const stripped = storedUser.branch_name
        .replace(/^Family Hostel\s+[—-]\s+/, "")
        .replace(/^Hotel\s+[—-]\s+/, "");
      if (stripped !== storedUser.branch_name) {
        storedUser.branch_name = stripped;
        localStorage.setItem("user", JSON.stringify(storedUser));
      }
    }
    setUser(storedUser);
    setIsAuthenticated(hasToken);

    // Re-fetch the live profile so any cached fields (e.g. branch_name
    // after a rebrand / branch rename) are refreshed without forcing a
    // re-login. Silent failure: if the call 401s the api interceptor
    // will handle logout.
    if (hasToken && storedUser?.id) {
      getAccount(storedUser.id)
        .then((fresh) => {
          if (fresh) {
            const merged = { ...storedUser, ...fresh };
            localStorage.setItem("user", JSON.stringify(merged));
            setUser(merged);
          }
        })
        .catch(() => { /* ignored — keep stale copy */ });
    }
  }, []);

  const login = useCallback(async (phone, password) => {
    const { user: userData } = await authService.login(phone, password);
    setUser(userData);
    setIsAuthenticated(true);
    navigate("/dashboard");
  }, [navigate]);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    setIsAuthenticated(false);
    navigate("/login");
  }, [navigate]);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated,
      login,
      logout,
    }),
    [user, isAuthenticated, login, logout]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export default AuthContext;
