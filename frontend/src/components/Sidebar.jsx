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
  { to: "/director/days-off", label: "📅 Day-Off Approvals" },
  { to: "/director/assignments", label: "👷 Task Assignment" },
  { to: "/director/penalties", label: "⚠️ Penalties" },
  { to: "/director/facility-logs", label: "🏗️ Facility Logs" },
  { to: "/director/shifts", label: "🕐 Shift Assignments" },
];

function SectionLabel({ children }) {
  return (
    <li style={{ padding: "12px 12px 4px", fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em" }}>
      {children}
    </li>
  );
}

function Sidebar() {
  const { user } = useAuth();
  const roles = user?.roles || [];

  const hasRole = (role) => roles.includes(role);
  const isStaff = hasRole("staff");
  const isAdmin = hasRole("administrator");
  const isDirector = hasRole("director");

  return (
    <aside
      style={{
        width: 220,
        minWidth: 220,
        padding: 16,
        borderRight: "1px solid #e0e0e0",
        background: "#fafafa",
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
      }}
    >
      <h3 style={{ margin: "0 0 24px", fontSize: 18 }}>FamilyHostel</h3>
      <nav>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {commonItems.map(({ to, label }) => (
            <li key={to} style={{ marginBottom: 2 }}>
              <NavLink
                to={to}
                style={({ isActive }) => ({
                  display: "block",
                  padding: "8px 12px",
                  borderRadius: 4,
                  color: isActive ? "#1a73e8" : "#333",
                  background: isActive ? "#e8f0fe" : "transparent",
                  fontWeight: isActive ? 600 : 400,
                  textDecoration: "none",
                  fontSize: 14,
                })}
              >
                {label}
              </NavLink>
            </li>
          ))}

          {isStaff && (
            <>
              <SectionLabel>Staff</SectionLabel>
              {staffItems.map(({ to, label }) => (
                <li key={to} style={{ marginBottom: 2 }}>
                  <NavLink
                    to={to}
                    style={({ isActive }) => ({
                      display: "block",
                      padding: "8px 12px",
                      borderRadius: 4,
                      color: isActive ? "#1a73e8" : "#333",
                      background: isActive ? "#e8f0fe" : "transparent",
                      fontWeight: isActive ? 600 : 400,
                      textDecoration: "none",
                      fontSize: 14,
                    })}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </>
          )}

          {isAdmin && (
            <>
              <SectionLabel>Admin</SectionLabel>
              {adminItems.map(({ to, label }) => (
                <li key={to} style={{ marginBottom: 2 }}>
                  <NavLink
                    to={to}
                    style={({ isActive }) => ({
                      display: "block",
                      padding: "8px 12px",
                      borderRadius: 4,
                      color: isActive ? "#1a73e8" : "#333",
                      background: isActive ? "#e8f0fe" : "transparent",
                      fontWeight: isActive ? 600 : 400,
                      textDecoration: "none",
                      fontSize: 14,
                    })}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </>
          )}

          {isDirector && (
            <>
              <SectionLabel>Director</SectionLabel>
              {directorItems.map(({ to, label }) => (
                <li key={to} style={{ marginBottom: 2 }}>
                  <NavLink
                    to={to}
                    style={({ isActive }) => ({
                      display: "block",
                      padding: "8px 12px",
                      borderRadius: 4,
                      color: isActive ? "#1a73e8" : "#333",
                      background: isActive ? "#e8f0fe" : "transparent",
                      fontWeight: isActive ? 600 : 400,
                      textDecoration: "none",
                      fontSize: 14,
                    })}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </>
          )}

          <SectionLabel>System</SectionLabel>
          <li style={{ marginBottom: 2 }}>
            <NavLink
              to="/reports"
              style={({ isActive }) => ({
                display: "block",
                padding: "8px 12px",
                borderRadius: 4,
                color: isActive ? "#1a73e8" : "#333",
                background: isActive ? "#e8f0fe" : "transparent",
                fontWeight: isActive ? 600 : 400,
                textDecoration: "none",
                fontSize: 14,
              })}
            >
              📈 Reports
            </NavLink>
          </li>
        </ul>
      </nav>
    </aside>
  );
}

export default Sidebar;
