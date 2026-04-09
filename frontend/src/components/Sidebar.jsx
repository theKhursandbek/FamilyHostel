import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/bookings", label: "Bookings" },
  { to: "/cleaning", label: "Cleaning" },
  { to: "/staff", label: "Staff" },
  { to: "/reports", label: "Reports" },
];

function Sidebar() {
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
      }}
    >
      <h3 style={{ margin: "0 0 24px", fontSize: 18 }}>FamilyHostel</h3>
      <nav>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {navItems.map(({ to, label }) => (
            <li key={to} style={{ marginBottom: 4 }}>
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
                })}
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}

export default Sidebar;
