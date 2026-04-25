import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { TelegramProvider } from "./context/TelegramContext.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <TelegramProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </TelegramProvider>
    </BrowserRouter>
  </StrictMode>
);
