import { createContext, useContext, useState, useCallback, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import * as authService from "../services/auth";

const AuthContext = createContext(null);

const ACTIVE_ROLE_KEY = "active_role";

// Highest-privilege wins when picking a default active role.
const ROLE_PRIORITY = ["superadmin", "director", "administrator", "staff", "client"];

function pickDefaultRole(roles) {
  if (!Array.isArray(roles) || roles.length === 0) return null;
  return ROLE_PRIORITY.find((r) => roles.includes(r)) || roles[0];
}

function loadActiveRole(roles) {
  const stored = localStorage.getItem(ACTIVE_ROLE_KEY);
  if (stored && roles?.includes(stored)) return stored;
  return pickDefaultRole(roles);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [isAuthenticated, setIsAuthenticated] = useState(() => authService.hasToken());
  const [activeRole, setActiveRole] = useState(() =>
    loadActiveRole(authService.getStoredUser()?.roles),
  );
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
      setActiveRole(null);
      return;
    }
    setUser(storedUser);
    setIsAuthenticated(hasToken);
    setActiveRole(loadActiveRole(storedUser?.roles));
  }, []);

  const login = useCallback(async (phone, password) => {
    const { user: userData } = await authService.login(phone, password);
    setUser(userData);
    setIsAuthenticated(true);
    const initialRole = pickDefaultRole(userData?.roles);
    setActiveRole(initialRole);
    if (initialRole) localStorage.setItem(ACTIVE_ROLE_KEY, initialRole);
    else localStorage.removeItem(ACTIVE_ROLE_KEY);
    navigate("/dashboard");
  }, [navigate]);

  const logout = useCallback(() => {
    authService.logout();
    localStorage.removeItem(ACTIVE_ROLE_KEY);
    setUser(null);
    setIsAuthenticated(false);
    setActiveRole(null);
    navigate("/login");
  }, [navigate]);

  const switchActiveRole = useCallback((role) => {
    setActiveRole(role);
    if (role) localStorage.setItem(ACTIVE_ROLE_KEY, role);
    else localStorage.removeItem(ACTIVE_ROLE_KEY);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated,
      login,
      logout,
      activeRole,
      setActiveRole: switchActiveRole,
    }),
    [user, isAuthenticated, login, logout, activeRole, switchActiveRole]
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

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export default AuthContext;
