import { createContext, useContext, useState, useCallback, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import * as authService from "../services/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [isAuthenticated, setIsAuthenticated] = useState(() => authService.hasToken());
  const navigate = useNavigate();

  // Sync state if token exists on mount
  useEffect(() => {
    const storedUser = authService.getStoredUser();
    const hasToken = authService.hasToken();
    setUser(storedUser);
    setIsAuthenticated(hasToken);
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
    () => ({ user, isAuthenticated, login, logout }),
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

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export default AuthContext;
