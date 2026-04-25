import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Mobile bottom navigation. Visible items adapt to the user's role:
 *   - Anonymous: Browse, Profile (login screen)
 *   - Client:    Browse, My Bookings, Profile
 *   - Staff:     Tasks, Browse, Profile
 */
function BottomNav() {
  const { user } = useAuth();
  const roles = user?.roles || [];
  const isStaff = roles.includes("staff");
  const isClient = roles.includes("client");

  return (
    <nav className="bottom-nav" aria-label="Primary">
      {isStaff && (
        <NavLink to="/staff" className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="nav-icon">🧹</span>
          Tasks
        </NavLink>
      )}

      <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="nav-icon">🏨</span>
        Browse
      </NavLink>

      {isClient && (
        <NavLink to="/me/bookings" className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="nav-icon">📅</span>
          Bookings
        </NavLink>
      )}

      <NavLink to="/me" className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="nav-icon">👤</span>
        Profile
      </NavLink>
    </nav>
  );
}

export default BottomNav;
