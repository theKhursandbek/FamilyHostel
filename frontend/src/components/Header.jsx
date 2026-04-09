import { useAuth } from "../context/AuthContext";

function Header() {
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
      }}
    >
      <span style={{ fontWeight: 500 }}>FamilyHostel Admin</span>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {user && (
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
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}

export default Header;
