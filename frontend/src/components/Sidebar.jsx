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
  Banknote,
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
  { to: "/admin/cash-sessions", label: "Cash Sessions", icon: Banknote },
  { to: "/admin/shifts", label: "Shift Assignments", icon: Clock },
];

const directorItems = [
  { to: "/director/days-off", label: "Day-Off Approvals", icon: CalendarDays },
  { to: "/director/penalties", label: "Penalties", icon: AlertTriangle },
  { to: "/director/facility-logs", label: "Facility Logs", icon: Building2 },
];

const superAdminItems = [
  { to: "/super-admin/users", label: "Users & Roles", icon: Users },
  { to: "/super-admin/branches", label: "Branches & Rooms", icon: Building2 },
  { to: "/super-admin/salary-settings", label: "Salary Settings", icon: Sliders },
  { to: "/super-admin/penalties", label: "Penalties", icon: AlertTriangle },
  { to: "/super-admin/expense-approvals", label: "Expense Approvals", icon: Building2 },
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
  const { user } = useAuth();
  const roles = user?.roles || [];

  const hasRole = (role) => roles.includes(role);
  const isStaff = hasRole("staff");
  const isSuperAdmin = hasRole("superadmin");
  // April 2026 unification: every Director also performs Administrator duties
  // for their branch via the same profile. So a Director sees BOTH the
  // Director and Admin sections. SuperAdmin (CEO) sees everything too.
  const isDirector = hasRole("director");
  const isAdmin = hasRole("administrator") || isDirector || isSuperAdmin;

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
