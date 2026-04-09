import { Outlet, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function MainLayout() {
  const { user, logout } = useAuth();

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Sidebar */}
      <aside style={{ width: 200, padding: 16, borderRight: "1px solid #ccc" }}>
        <h3>FamilyHostel</h3>
        <nav>
          <ul style={{ listStyle: "none", padding: 0 }}>
            <li>
              <Link to="/dashboard">Dashboard</Link>
            </li>
          </ul>
        </nav>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1 }}>
        {/* Header */}
        <header
          style={{
            padding: 16,
            borderBottom: "1px solid #ccc",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>FamilyHostel Admin</span>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {user && <span>{user.phone}</span>}
            <button
              onClick={logout}
              style={{
                padding: "6px 12px",
                background: "none",
                border: "1px solid #ccc",
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              Logout
            </button>
          </div>
        </header>

        {/* Page content */}
        <main style={{ padding: 16 }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default MainLayout;
