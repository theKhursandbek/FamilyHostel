import { useAuth } from "../context/AuthContext";
import MainLayout from "./MainLayout";
import StaffLayout from "./StaffLayout";

const PRIVILEGED = new Set(["administrator", "director", "superadmin"]);

/**
 * Picks the right shell for the signed-in user.
 *
 * Pure Staff (no admin/director/superadmin role) get the lightweight
 * mobile/PWA StaffLayout with a bottom tab bar. Everyone else keeps the
 * full desktop MainLayout with the sidebar.
 */
function AppShell() {
  const { user } = useAuth();
  const roles = user?.roles || [];
  const isStaffOnly =
    roles.includes("staff") && !roles.some((r) => PRIVILEGED.has(r));

  return isStaffOnly ? <StaffLayout /> : <MainLayout />;
}

export default AppShell;
