import { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Menu, ChevronDown, LogOut, Repeat } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const ROLE_LABEL = {
  superadmin: "CEO",
  director: "Director",
  administrator: "Administrator",
  staff: "Staff",
};

// Roles that may be switched between when an account holds both.
const SWITCHABLE_ROLES = ["director", "administrator"];

/**
 * Compact top app bar.
 *
 * - Hamburger appears only on mobile (sidebar is sticky on desktop).
 * - When the account holds two switchable roles (Director + Administrator),
 *   a Switch pill appears so the user can flip dashboards in one click.
 * - Right side shows a single user pill that opens a dropdown menu
 *   containing "Signed in as ..." + Sign out.
 */
function Header({ onToggleSidebar, isMobile }) {
  const { user, logout, activeRole, setActiveRole } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const wrapperRef = useRef(null);

  const userRoles = user?.roles || [];
  const switchableHeld = SWITCHABLE_ROLES.filter((r) => userRoles.includes(r));
  const canSwitch = switchableHeld.length === 2;
  const displayRole = activeRole || userRoles[0];
  const friendlyRole = ROLE_LABEL[displayRole] || "User";
  const fullName = user?.full_name?.trim() || friendlyRole;
  const phone = user?.phone || "";
  const branchName = user?.branch_name || "";
  // "Director of Unusabad branch" — only append branch line if both pieces exist
  const roleLine = branchName
    ? `${friendlyRole} of ${branchName} branch`
    : friendlyRole;
  const initial = (fullName || friendlyRole).charAt(0).toUpperCase();

  const handleSwitchRole = () => {
    if (!canSwitch) return;
    const other = switchableHeld.find((r) => r !== activeRole) || switchableHeld[0];
    setActiveRole(other);
  };
  const otherRoleLabel = canSwitch
    ? ROLE_LABEL[switchableHeld.find((r) => r !== activeRole) || switchableHeld[0]]
    : "";

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
          {canSwitch && (
            <button
              type="button"
              className="header-role-switch"
              onClick={handleSwitchRole}
              title={`Switch to ${otherRoleLabel} dashboard`}
              aria-label={`Switch to ${otherRoleLabel} dashboard`}
            >
              <Repeat size={14} strokeWidth={1.8} aria-hidden="true" />
              {!isMobile && (
                <span style={{ marginLeft: 6 }}>
                  Switch to {otherRoleLabel}
                </span>
              )}
            </button>
          )}

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
