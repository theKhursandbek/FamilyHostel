import { NavLink } from "react-router-dom";
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

const linkStyle = ({ isActive }) => ({
  display: "block",
  padding: "8px 12px",
  borderRadius: 4,
  color: isActive ? "#1a73e8" : "#333",
  background: isActive ? "#e8f0fe" : "transparent",
  fontWeight: isActive ? 600 : 400,
  textDecoration: "none",
  fontSize: 14,
});

function SectionLabel({ children }) {
  return (
    <li style={{ padding: "12px 12px 4px", fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em" }}>
      {children}
    </li>
  );
}

function NavItems({ items, onNavigate }) {
  return items.map(({ to, label }) => (
    <li key={to} style={{ marginBottom: 2 }}>
      <NavLink to={to} style={linkStyle} onClick={onNavigate}>
        {label}
      </NavLink>
    </li>
  ));
}

function Sidebar({ isOpen, isMobile, onClose }) {
  const { user } = useAuth();
  const roles = user?.roles || [];

  const hasRole = (role) => roles.includes(role);
  const isStaff = hasRole("staff");
  const isAdmin = hasRole("administrator");
  const isDirector = hasRole("director");
  const isSuperAdmin = hasRole("super_admin");

  // On mobile, close sidebar after clicking a link
  const handleNavigate = isMobile ? onClose : undefined;

  return (
    <aside className={`sidebar${isOpen ? " open" : ""}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h3 style={{ margin: 0, fontSize: 18 }}>FamilyHostel</h3>
        {isMobile && (
          <button
            onClick={onClose}
            style={{
              padding: "2px 8px",
              background: "none",
              border: "1px solid #dadce0",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: 16,
              lineHeight: 1,
            }}
            aria-label="Close sidebar"
          >
            ✕
          </button>
        )}
      </div>

      <nav style={{ flex: 1, overflowY: "auto" }}>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
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

export default Sidebar;
