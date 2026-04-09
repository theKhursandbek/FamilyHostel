import { useState, useEffect, useCallback } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";

function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const location = useLocation();

  // Detect mobile breakpoint
  const checkMobile = useCallback(() => {
    setIsMobile(globalThis.innerWidth <= 768);
  }, []);

  useEffect(() => {
    checkMobile();
    globalThis.addEventListener("resize", checkMobile);
    return () => globalThis.removeEventListener("resize", checkMobile);
  }, [checkMobile]);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    }
  }, [location.pathname, isMobile]);

  const toggleSidebar = () => setSidebarOpen((prev) => !prev);
  const closeSidebar = () => setSidebarOpen(false);

  return (
    <div style={{ display: "flex", minHeight: "100vh", overflow: "hidden" }}>
      {/* Backdrop for mobile drawer */}
      {isMobile && (
        <div
          className={`sidebar-backdrop${sidebarOpen ? " active" : ""}`}
          onClick={closeSidebar}
        />
      )}

      <Sidebar
        isOpen={sidebarOpen}
        isMobile={isMobile}
        onClose={closeSidebar}
      />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header
          onToggleSidebar={toggleSidebar}
          isMobile={isMobile}
        />

        <main className="layout-main" style={{ flex: 1, padding: 24, overflowX: "hidden" }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default MainLayout;
