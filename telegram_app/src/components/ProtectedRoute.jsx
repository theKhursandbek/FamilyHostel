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
    const here = `${location.pathname}${location.search || ""}`;
    const next = encodeURIComponent(here);
    return <Navigate to={`/login?next=${next}`} replace state={{ from: here }} />;
  }

  // First-time accounts must finish registration before reaching any
  // protected page.
  if (user?.is_new && location.pathname !== "/register") {
    const here = `${location.pathname}${location.search || ""}`;
    const next = encodeURIComponent(here);
    return <Navigate to={`/register?next=${next}`} replace />;
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
