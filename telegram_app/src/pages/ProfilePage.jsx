import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTelegram } from "../context/TelegramContext";

const ROLE_LABEL = {
  superadmin: "Super Admin",
  director: "Director",
  administrator: "Administrator",
  staff: "Staff",
  client: "Guest",
};

/**
 * Profile / hub page.
 *
 * Anonymous → links to /login.
 * Client    → links to bookings.
 * Staff     → links to staff dashboard.
 */
function ProfilePage() {
  const { user, isAuthenticated, logout } = useAuth();
  const { user: tgUser, isInsideTelegram } = useTelegram();

  if (!isAuthenticated) {
    return (
      <div>
        <h1>Welcome</h1>
        <p className="text-hint">
          Sign in to book rooms or manage your shifts.
        </p>
        <Link to="/login" className="btn" style={{ marginTop: 16 }}>
          Sign in
        </Link>
      </div>
    );
  }

  const roles = user?.roles || [];
  const isStaff = roles.includes("staff");
  const isClient = roles.includes("client");

  return (
    <div>
      <h1>
        {tgUser?.first_name || "Account"}
        {tgUser?.last_name ? ` ${tgUser.last_name}` : ""}
      </h1>

      <div className="card">
        <div className="card-title">Roles</div>
        <div className="card-subtitle">
          {roles.length
            ? roles.map((r) => ROLE_LABEL[r] || r).join(" · ")
            : "No active roles"}
        </div>
      </div>

      {!isInsideTelegram && (
        <p className="text-hint" style={{ marginTop: 8 }}>
          Demo session (signed in via phone). Inside Telegram you'd be
          recognised automatically.
        </p>
      )}

      {isStaff && (
        <Link to="/staff" className="card">
          <div className="card-title">🧹 Staff Dashboard</div>
          <div className="card-subtitle">Tasks, days off, penalties.</div>
        </Link>
      )}

      {isClient && (
        <Link to="/me/bookings" className="card">
          <div className="card-title">📅 My Bookings</div>
          <div className="card-subtitle">Past and upcoming reservations.</div>
        </Link>
      )}

      <button
        type="button"
        className="btn btn-secondary"
        style={{ marginTop: 24 }}
        onClick={logout}
      >
        Sign out
      </button>
    </div>
  );
}

export default ProfilePage;
