import { NavLink } from "react-router-dom";
import {
  Home,
  CheckCircle2,
  Banknote,
  CalendarDays,
  User,
} from "lucide-react";

const TABS = [
  { to: "/dashboard", label: "Home", icon: Home, end: true },
  { to: "/staff/my-tasks", label: "Tasks", icon: CheckCircle2 },
  { to: "/salary", label: "Salary", icon: Banknote },
  { to: "/staff/days-off", label: "Days Off", icon: CalendarDays },
  { to: "/staff/penalties", label: "Me", icon: User },
];

/**
 * Floating glass-pill bottom nav for the staff mobile/PWA shell — styled to
 * match the Telegram Mini App. Five thumb-reachable destinations; the active
 * tab gets a filled pill, and on narrow phones inactive labels collapse to
 * icon-only. Safe-area aware via CSS env(safe-area-inset-bottom).
 */
function StaffBottomNav() {
  return (
    <nav className="staff-nav" aria-label="Staff navigation">
      {TABS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `staff-nav__item${isActive ? " is-active" : ""}`
          }
        >
          <span className="staff-nav__ico">
            {Icon && <Icon size={24} strokeWidth={1.8} aria-hidden />}
          </span>
          <span className="staff-nav__lbl">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export default StaffBottomNav;
