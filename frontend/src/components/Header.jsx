import { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Menu, ChevronDown, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const ROLE_LABEL = {
  superadmin: "CEO",
  director: "Director",
  administrator: "Administrator",
  staff: "Staff",
};

// Highest-privilege wins when picking the display role.
const ROLE_PRIORITY = ["superadmin", "director", "administrator", "staff", "client"];
function pickDisplayRole(roles) {
  if (!Array.isArray(roles) || roles.length === 0) return null;
  return ROLE_PRIORITY.find((r) => roles.includes(r)) || roles[0];
}

/**
 * Compact top app bar.
 *
 * - Hamburger appears only on mobile (sidebar is sticky on desktop).
 * - Right side shows a single user pill that opens a dropdown menu
 *   containing "Signed in as ..." + Sign out.
 */
function Header({ onToggleSidebar, isMobile }) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const wrapperRef = useRef(null);

  const userRoles = user?.roles || [];
  const displayRole = pickDisplayRole(userRoles);
  const friendlyRole = ROLE_LABEL[displayRole] || "User";
  const fullName = user?.full_name?.trim() || friendlyRole;
  const phone = user?.phone || "";
  const branchName = user?.branch_name || "";
  // "Director of Unusabad branch" — only append branch line if both pieces exist
  const roleLine = branchName
    ? `${friendlyRole} of ${branchName} branch`
    : friendlyRole;
  const initial = (fullName || friendlyRole).charAt(0).toUpperCase();

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onDocClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  return (
    <header className="header">
      {isMobile && (
        <button
          type="button"
          className="header-toggle"
          onClick={onToggleSidebar}
          aria-label="Open sidebar"
        >
          <Menu size={18} strokeWidth={1.8} />
        </button>
      )}

      {user && (
        <div className="header-actions" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <div className="header-user-wrapper" ref={wrapperRef}>
          <button
            type="button"
            className={`header-user${menuOpen ? " open" : ""}`}
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <span className="header-avatar" aria-hidden="true">{initial}</span>
            {!isMobile && (
              <span className="header-user-meta">
                <span className="header-user-name">{fullName}</span>
                <span className="header-user-role">{roleLine}</span>
              </span>
            )}
            <ChevronDown size={14} strokeWidth={1.8} className="header-user-chevron" aria-hidden="true" />
          </button>

          {menuOpen && (
            <div className="header-user-menu" role="menu">
              <div className="header-user-menu-meta">
                <div className="header-user-menu-name">{fullName}</div>
                <div className="header-user-menu-role">{roleLine}</div>
                {phone && <div className="header-user-menu-phone">{phone}</div>}
              </div>
              <button
                type="button"
                className="header-user-menu-signout"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
              >
                <LogOut size={16} strokeWidth={1.8} aria-hidden="true" /> Sign out
              </button>
            </div>
          )}
        </div>
        </div>
      )}
    </header>
  );
}

Header.propTypes = {
  onToggleSidebar: PropTypes.func.isRequired,
  isMobile: PropTypes.bool.isRequired,
};

export default Header;
