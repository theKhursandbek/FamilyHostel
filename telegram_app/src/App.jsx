import { Routes, Route, Navigate } from "react-router-dom";
import BottomNav from "./components/BottomNav";
import DeepLinkHandler from "./components/DeepLinkHandler";
import ProtectedRoute from "./components/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import OfflineBanner from "./components/OfflineBanner";

// Public catalogue
import CataloguePage from "./pages/CataloguePage";
import RoomDetailPage from "./pages/public/RoomDetailPage";

// Auth + profile
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ProfilePage from "./pages/ProfilePage";
import ProfileEditPage from "./pages/ProfileEditPage";

// Client booking flow
import MyBookingsPage from "./pages/client/MyBookingsPage";
import BookingFlowPage from "./pages/client/BookingFlowPage";
import BookingDetailPage from "./pages/client/BookingDetailPage";
import ExtendFlowPage from "./pages/client/ExtendFlowPage";
import PaymentPage from "./pages/client/PaymentPage";
import ChangePasswordPage from "./pages/client/ChangePasswordPage";

// Auth extras
import ForgotPasswordPage from "./pages/ForgotPasswordPage";

/**
 * Telegram Mini App router.
 *
 * Auth model:
 *   - Home + room detail are public (browse without login).
 *   - Profile, MyBookings, Booking flow, Payment, Extend all require auth.
 *   - First-time accounts (is_new) are forced through /register.
 */
function App() {
  return (
    <ErrorBoundary>
      <OfflineBanner />
      <DeepLinkHandler />
      <main className="app-main">
        <Routes>
          {/* Public catalogue */}
          <Route path="/" element={<CataloguePage />} />
          <Route path="/rooms/:id" element={<RoomDetailPage />} />

          {/* Auth */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          {/* Protected — Profile + Bookings + Booking flow + Payment + Extend */}
          <Route path="/me" element={
            <ProtectedRoute><ProfilePage /></ProtectedRoute>
          } />
          <Route path="/me/edit" element={
            <ProtectedRoute><ProfileEditPage /></ProtectedRoute>
          } />
          <Route path="/me/bookings" element={
            <ProtectedRoute><MyBookingsPage /></ProtectedRoute>
          } />
          <Route path="/me/bookings/:id" element={
            <ProtectedRoute><BookingDetailPage /></ProtectedRoute>
          } />
          <Route path="/me/bookings/:id/extend" element={
            <ProtectedRoute requireRole={["client"]}><ExtendFlowPage /></ProtectedRoute>
          } />
          <Route path="/me/change-password" element={
            <ProtectedRoute><ChangePasswordPage /></ProtectedRoute>
          } />
          <Route path="/book/:roomId" element={
            <ProtectedRoute><BookingFlowPage /></ProtectedRoute>
          } />
          <Route path="/pay/:draftId" element={
            <ProtectedRoute><PaymentPage /></ProtectedRoute>
          } />

          {/* 404 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <BottomNav />
    </ErrorBoundary>
  );
}

export default App;
