import { Routes, Route, Navigate } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import BookingsPage from "./pages/BookingsPage";
import BookingDetailPage from "./pages/BookingDetailPage";
import CleaningPage from "./pages/CleaningPage";
import ReportsPage from "./pages/reports/ReportsPage";
import ProtectedRoute from "./components/ProtectedRoute";

// Salary page
import SalaryPage from "./pages/salary/SalaryPage";

// Staff pages
import MyTasksPage from "./pages/staff/MyTasksPage";
import DaysOffPage from "./pages/staff/DaysOffPage";
import PenaltiesViewPage from "./pages/staff/PenaltiesViewPage";

// Admin pages
import RoomInspectionPage from "./pages/admin/RoomInspectionPage";
import CashSessionPage from "./pages/admin/CashSessionPage";

// Director pages
import DaysOffApprovalPage from "./pages/director/DaysOffApprovalPage";
import TaskAssignmentPage from "./pages/director/TaskAssignmentPage";
import PenaltyManagementPage from "./pages/director/PenaltyManagementPage";
import FacilityLogsPage from "./pages/director/FacilityLogsPage";
import ShiftAssignmentPage from "./pages/director/ShiftAssignmentPage";
import DirectorDashboard from "./pages/director/DirectorDashboard";

// Super Admin pages
import SuperAdminDashboard from "./pages/superadmin/SuperAdminDashboard";

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected routes inside layout */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="bookings" element={<BookingsPage />} />
        <Route path="bookings/:id" element={<BookingDetailPage />} />
        <Route path="cleaning" element={<CleaningPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="salary" element={<SalaryPage />} />

        {/* Staff routes */}
        <Route path="staff/my-tasks" element={<MyTasksPage />} />
        <Route path="staff/days-off" element={<DaysOffPage />} />
        <Route path="staff/penalties" element={<PenaltiesViewPage />} />

        {/* Admin routes */}
        <Route path="admin/inspections" element={<RoomInspectionPage />} />
        <Route path="admin/cash-sessions" element={<CashSessionPage />} />

        {/* Director routes */}
        <Route path="director/days-off" element={<DaysOffApprovalPage />} />
        <Route path="director/assignments" element={<TaskAssignmentPage />} />
        <Route path="director/penalties" element={<PenaltyManagementPage />} />
        <Route path="director/facility-logs" element={<FacilityLogsPage />} />
        <Route path="director/shifts" element={<ShiftAssignmentPage />} />
        <Route path="director/dashboard" element={<DirectorDashboard />} />

        {/* Super Admin routes */}
        <Route path="super-admin/dashboard" element={<SuperAdminDashboard />} />

        {/* 404 catch-all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
