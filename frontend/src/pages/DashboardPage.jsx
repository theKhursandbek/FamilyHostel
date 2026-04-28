import PropTypes from "prop-types";
import { useAuth } from "../context/AuthContext";
import AdminDashboard from "./admin/AdminDashboard";
import DirectorDashboard from "./director/DirectorDashboard";
import SuperAdminDashboard from "./superadmin/SuperAdminDashboard";
import StaffDashboard from "./staff/StaffDashboard";

const ROLE_LABEL = {
  superadmin: "CEO",
  director: "Director",
  administrator: "Administrator",
  staff: "Staff",
};

function getGreeting(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function GreetingHero({ user }) {
  const now = new Date();
  const greeting = getGreeting(now.getHours());
  const dateStr = now.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const role = user?.roles?.[0];
  const friendlyName =
    user?.full_name?.trim() || ROLE_LABEL[role] || user?.phone || "there";

  return (
    <section className="greeting">
      <div className="greeting-meta">{dateStr}</div>
      <h1>
        {greeting}, <span className="name">{friendlyName}</span>
      </h1>
      <div className="greeting-sub">
        Here&apos;s your personalised hostel dashboard.
      </div>
    </section>
  );
}

GreetingHero.propTypes = {
  user: PropTypes.shape({
    full_name: PropTypes.string,
    phone: PropTypes.string,
    roles: PropTypes.arrayOf(PropTypes.string),
  }),
};

GreetingHero.defaultProps = { user: null };

/**
 * Role-aware dashboard router.
 *
 * The single "/dashboard" route is shared across all admin-panel users
 * (Super Admin, Director, Administrator, Staff). Each role gets its
 * own dedicated dashboard component, picked here in priority order
 * (highest privilege wins when a user has multiple roles).
 *
 * Why a router instead of one fat component?
 *  - Each backend endpoint requires a specific profile (administrator,
 *    director, super_admin). Calling the wrong one returns HTTP 400.
 *  - Each role-specific dashboard already exists and owns its own
 *    data fetching + WebSocket channel.
 *  - Keeps role-specific UI isolated and testable.
 */
function DashboardPage() {
  const { user } = useAuth();
  const roles = user?.roles || [];

  // Pick highest-privilege dashboard the account holds. Role switching was
  // removed in Phase 1 (2026-04 refactor): Director ⊇ Administrator on the
  // same branch, so a Director never needs the Admin dashboard.
  let RoleDashboard = null;
  if (roles.includes("superadmin")) RoleDashboard = SuperAdminDashboard;
  else if (roles.includes("director")) RoleDashboard = DirectorDashboard;
  else if (roles.includes("administrator")) RoleDashboard = AdminDashboard;
  else if (roles.includes("staff")) RoleDashboard = StaffDashboard;

  if (RoleDashboard) {
    return (
      <>
        <GreetingHero user={user} />
        <RoleDashboard />
      </>
    );
  }

  // Fallback for accounts with no recognised role
  return (
    <div>
      <GreetingHero user={user} />
      <div className="empty-state">
        Your account has no role assigned yet. Please contact a Super Admin.
      </div>
    </div>
  );
}

export default DashboardPage;
