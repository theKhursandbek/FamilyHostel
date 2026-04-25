import PropTypes from "prop-types";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Auth guard. If `requireRole` is set, also enforces that the signed-in
 * user holds at least one of the listed roles.
 */
function ProtectedRoute({ children, requireRole }) {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (requireRole?.length) {
    const roles = user?.roles || [];
    const ok = requireRole.some((r) => roles.includes(r));
    if (!ok) return <Navigate to="/me" replace />;
  }

  return children;
}

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
  requireRole: PropTypes.arrayOf(PropTypes.string),
};

export default ProtectedRoute;
