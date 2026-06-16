import { Outlet } from "react-router-dom";
import StaffBottomNav from "../components/StaffBottomNav";

/**
 * Staff-only mobile/PWA shell — modelled exactly on the Telegram Mini App.
 *
 * Like telegram_app there is NO persistent top bar: each page renders its own
 * hero, the routed page scrolls in the middle, and a floating glass-pill
 * bottom nav handles navigation. Sign-out lives on the "Me" tab.
 */
function StaffLayout() {
  return (
    <div className="staff-shell">
      <main className="staff-shell__main">
        <Outlet />
      </main>

      <StaffBottomNav />
    </div>
  );
}

export default StaffLayout;
