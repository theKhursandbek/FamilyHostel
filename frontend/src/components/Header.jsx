import { useAuth } from "../context/AuthContext";

function Header({ onToggleSidebar, isMobile }) {
  const { user, logout } = useAuth();

  return (
    <header
      style={{
        padding: "12px 24px",
        borderBottom: "1px solid #e0e0e0",
        background: "#fff",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* Sidebar toggle (hamburger) */}
        <button
          onClick={onToggleSidebar}
          style={{
            padding: "4px 8px",
            background: "none",
            border: "1px solid #dadce0",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 18,
            lineHeight: 1,
            display: "flex",
            alignItems: "center",
          }}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>
        <span className="header-title" style={{ fontWeight: 500 }}>
          {isMobile ? "FH" : "FamilyHostel Admin"}
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {user && !isMobile && (
          <span style={{ color: "#666", fontSize: 14 }}>{user.phone}</span>
        )}
        <button
          onClick={logout}
          style={{
            padding: "6px 14px",
            background: "none",
            border: "1px solid #ccc",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
            whiteSpace: "nowrap",
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}

export default Header;
