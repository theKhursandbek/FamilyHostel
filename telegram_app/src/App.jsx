import { Routes, Route, Navigate } from "react-router-dom";
import BottomNav from "./components/BottomNav";
import ProtectedRoute from "./components/ProtectedRoute";

// Public
import HomePage from "./pages/public/HomePage";
import BranchDetailPage from "./pages/public/BranchDetailPage";
import RoomDetailPage from "./pages/public/RoomDetailPage";

// Auth + profile
import LoginPage from "./pages/LoginPage";
import ProfilePage from "./pages/ProfilePage";

// Authenticated areas
import MyBookingsPage from "./pages/client/MyBookingsPage";
import StaffDashboardPage from "./pages/staff/StaffDashboardPage";

/**
 * Telegram Mini App router.
 *
 * Layout: a single scrollable <main> + a fixed bottom-nav. Routes are
 * organised by audience (public / client / staff) and protected per role.
 */
function App() {
  return (
    <>
      <main className="app-main">
        <Routes>
          {/* Public — no auth required */}
          <Route path="/" element={<HomePage />} />
          <Route path="/branches/:id" element={<BranchDetailPage />} />
          <Route path="/rooms/:id" element={<RoomDetailPage />} />

          {/* Auth */}
          <Route path="/login" element={<LoginPage />} />

          {/* Profile (any signed-in user, or anonymous → login prompt). */}
          <Route path="/me" element={<ProfilePage />} />

          {/* Client area */}
          <Route
            path="/me/bookings"
            element={
              <ProtectedRoute requireRole={["client"]}>
                <MyBookingsPage />
              </ProtectedRoute>
            }
          />

          {/* Staff area */}
          <Route
            path="/staff"
            element={
              <ProtectedRoute requireRole={["staff", "administrator", "director", "superadmin"]}>
                <StaffDashboardPage />
              </ProtectedRoute>
            }
          />

          {/* 404 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <BottomNav />
    </>
  );
}

export default App;
