import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";

function MainLayout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />

      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <Header />

        <main style={{ flex: 1, padding: 24 }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default MainLayout;
