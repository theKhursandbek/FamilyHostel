import { useAuth } from "../context/AuthContext";

function Header({ onToggleSidebar, isMobile }) {
  const { user, logout } = useAuth();

  return (
    <header className="header">
      <div className="header-left">
        <button className="header-toggle" onClick={onToggleSidebar} aria-label="Toggle sidebar">
          ☰
        </button>
        <span className="header-title">
          {isMobile ? "FH" : "FamilyHostel Admin"}
        </span>
      </div>

      <div className="header-right">
        {user && !isMobile && (
          <span className="header-phone">{user.phone}</span>
        )}
        <button className="header-logout" onClick={logout}>
          Logout
        </button>
      </div>
    </header>
  );
}

export default Header;
