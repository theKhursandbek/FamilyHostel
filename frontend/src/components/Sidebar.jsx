import { NavLink } from "react-router-dom";
import PropTypes from "prop-types";
import {
  LayoutDashboard,
  ClipboardList,
  Sparkles,
  TrendingUp,
  Wallet,
  CheckCircle2,
  CalendarDays,
  AlertTriangle,
  Search,
  Banknote,
  HardHat,
  Building2,
  Clock,
  Users,
  Sliders,
  ShieldAlert,
  Activity,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const ICON_PROPS = { size: 18, strokeWidth: 1.6 };

const commonItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/bookings", label: "Bookings", icon: ClipboardList },
  { to: "/cleaning", label: "Cleaning", icon: Sparkles },
  { to: "/reports", label: "Reports", icon: TrendingUp },
  { to: "/salary", label: "Salary", icon: Wallet },
];

const staffItems = [
  { to: "/staff/my-tasks", label: "My Tasks", icon: CheckCircle2 },
  { to: "/staff/days-off", label: "Days Off", icon: CalendarDays },
  { to: "/staff/penalties", label: "My Penalties", icon: AlertTriangle },
];

const adminItems = [
  { to: "/admin/inspections", label: "Inspections", icon: Search },
  { to: "/admin/cash-sessions", label: "Cash Sessions", icon: Banknote },
];

const directorItems = [
  { to: "/director/days-off", label: "Day-Off Approvals", icon: CalendarDays },
  { to: "/director/assignments", label: "Task Assignment", icon: HardHat },
  { to: "/director/penalties", label: "Penalties", icon: AlertTriangle },
  { to: "/director/facility-logs", label: "Facility Logs", icon: Building2 },
  { to: "/director/shifts", label: "Shift Assignments", icon: Clock },
];

const superAdminItems = [
  { to: "/super-admin/users", label: "Users & Roles", icon: Users },
  { to: "/super-admin/branches", label: "Branches & Rooms", icon: Building2 },
  { to: "/super-admin/salary-settings", label: "Salary Settings", icon: Sliders },
  { to: "/super-admin/activity", label: "Live Activity", icon: Activity },
  { to: "/super-admin/override", label: "Override", icon: ShieldAlert },
];

function SectionLabel({ children }) {
  return <li className="sidebar-section">{children}</li>;
}

SectionLabel.propTypes = {
  children: PropTypes.node.isRequired,
};

function NavItems({ items, onNavigate }) {
  return items.map(({ to, label, icon: Icon }) => (
    <li key={to}>
      <NavLink
        to={to}
        className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
        onClick={onNavigate}
      >
        {Icon && <Icon {...ICON_PROPS} className="sidebar-link-icon" aria-hidden="true" />}
        <span>{label}</span>
      </NavLink>
    </li>
  ));
}

NavItems.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.shape({
      to: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      icon: PropTypes.elementType,
    })
  ).isRequired,
  onNavigate: PropTypes.func,
};

function Sidebar({ isOpen, isMobile, onClose }) {
  const { user, activeRole } = useAuth();
  const roles = user?.roles || [];

  const hasRole = (role) => roles.includes(role);
  const isStaff = hasRole("staff");
  const isSuperAdmin = hasRole("superadmin");

  // For accounts that hold both Director and Administrator profiles, show
  // ONLY the active role's section so the sidebar stays uncluttered. The
  // user can flip via the Switch button in the Header.
  const holdsAdmin = hasRole("administrator");
  const holdsDirector = hasRole("director");
  const dualHolder = holdsAdmin && holdsDirector;
  const isAdmin = dualHolder ? activeRole === "administrator" : holdsAdmin;
  const isDirector = dualHolder ? activeRole === "director" : holdsDirector;

  const handleNavigate = isMobile ? onClose : undefined;

  return (
    <aside className={`sidebar${isOpen ? " open" : ""}`}>
      <div className="sidebar-brand">
        <h3>FamilyHostel</h3>
        {isMobile && (
          <button type="button" className="sidebar-close" onClick={onClose} aria-label="Close sidebar">
            <X size={16} strokeWidth={1.8} />
          </button>
        )}
      </div>

      <nav style={{ flex: 1, overflow: "hidden" }}>
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
              <SectionLabel>CEO</SectionLabel>
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
