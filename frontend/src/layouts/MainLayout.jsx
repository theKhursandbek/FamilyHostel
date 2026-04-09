import { Outlet, Link } from "react-router-dom";

function MainLayout() {
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
            <li>
              <Link to="/login">Login</Link>
            </li>
          </ul>
        </nav>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1 }}>
        {/* Header */}
        <header style={{ padding: 16, borderBottom: "1px solid #ccc" }}>
          <span>FamilyHostel Admin</span>
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
