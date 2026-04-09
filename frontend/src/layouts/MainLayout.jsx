import { useState, useEffect, useCallback } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";

function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const location = useLocation();

  const checkMobile = useCallback(() => {
    setIsMobile(globalThis.innerWidth <= 768);
  }, []);

  useEffect(() => {
    checkMobile();
    globalThis.addEventListener("resize", checkMobile);
    return () => globalThis.removeEventListener("resize", checkMobile);
  }, [checkMobile]);

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [location.pathname, isMobile]);

  const toggleSidebar = () => setSidebarOpen((prev) => !prev);
  const closeSidebar = () => setSidebarOpen(false);

  return (
    <div className="layout">
      {isMobile && (
        <button
          type="button"
          className={`sidebar-backdrop${sidebarOpen ? " active" : ""}`}
          aria-label="Close sidebar"
          onClick={closeSidebar}
        />
      )}

      <Sidebar isOpen={sidebarOpen} isMobile={isMobile} onClose={closeSidebar} />

      <div className="layout-body">
        <Header onToggleSidebar={toggleSidebar} isMobile={isMobile} />
        <main className="layout-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default MainLayout;
