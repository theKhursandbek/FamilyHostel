import { NavLink } from "react-router-dom";
import PropTypes from "prop-types";
import { useAuth } from "../context/AuthContext";

const commonItems = [
  { to: "/dashboard", label: "📊 Dashboard" },
  { to: "/bookings", label: "📋 Bookings" },
  { to: "/cleaning", label: "🧹 Cleaning" },
  { to: "/reports", label: "📈 Reports" },
  { to: "/salary", label: "💰 Salary" },
];

const staffItems = [
  { to: "/staff/my-tasks", label: "✅ My Tasks" },
  { to: "/staff/days-off", label: "📅 Days Off" },
  { to: "/staff/penalties", label: "⚠️ My Penalties" },
];

const adminItems = [
  { to: "/admin/inspections", label: "🔍 Inspections" },
  { to: "/admin/cash-sessions", label: "💰 Cash Sessions" },
];

const directorItems = [
  { to: "/director/dashboard", label: "🏢 Director Dashboard" },
  { to: "/director/days-off", label: "📅 Day-Off Approvals" },
  { to: "/director/assignments", label: "👷 Task Assignment" },
  { to: "/director/penalties", label: "⚠️ Penalties" },
  { to: "/director/facility-logs", label: "🏗️ Facility Logs" },
  { to: "/director/shifts", label: "🕐 Shift Assignments" },
];

const superAdminItems = [
  { to: "/super-admin/dashboard", label: "🛡️ Super Admin Dashboard" },
];

function SectionLabel({ children }) {
  return <li className="sidebar-section">{children}</li>;
}

SectionLabel.propTypes = {
  children: PropTypes.node.isRequired,
};

function NavItems({ items, onNavigate }) {
  return items.map(({ to, label }) => (
    <li key={to}>
      <NavLink
        to={to}
        className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
        onClick={onNavigate}
      >
        {label}
      </NavLink>
    </li>
  ));
}

NavItems.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.shape({
      to: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
    })
  ).isRequired,
  onNavigate: PropTypes.func,
};

function Sidebar({ isOpen, isMobile, onClose }) {
  const { user } = useAuth();
  const roles = user?.roles || [];

  const hasRole = (role) => roles.includes(role);
  const isStaff = hasRole("staff");
  const isAdmin = hasRole("administrator");
  const isDirector = hasRole("director");
  const isSuperAdmin = hasRole("super_admin");

  const handleNavigate = isMobile ? onClose : undefined;

  return (
    <aside className={`sidebar${isOpen ? " open" : ""}`}>
      <div className="sidebar-brand">
        <h3>FamilyHostel</h3>
        {isMobile && (
          <button className="sidebar-close" onClick={onClose} aria-label="Close sidebar">
            ✕
          </button>
        )}
      </div>

      <nav style={{ flex: 1, overflowY: "auto" }}>
        <ul className="sidebar-nav">
          <NavItems items={commonItems} onNavigate={handleNavigate} />

          {isStaff && (
            <>
              <SectionLabel>Staff</SectionLabel>
              <NavItems items={staffItems} onNavigate={handleNavigate} />
            </>
          )}

          {isAdmin && (
            <>
              <SectionLabel>Admin</SectionLabel>
              <NavItems items={adminItems} onNavigate={handleNavigate} />
            </>
          )}

          {isDirector && (
            <>
              <SectionLabel>Director</SectionLabel>
              <NavItems items={directorItems} onNavigate={handleNavigate} />
            </>
          )}

          {isSuperAdmin && (
            <>
              <SectionLabel>Super Admin</SectionLabel>
              <NavItems items={superAdminItems} onNavigate={handleNavigate} />
            </>
          )}
        </ul>
      </nav>
    </aside>
  );
}

Sidebar.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  isMobile: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

export default Sidebar;
