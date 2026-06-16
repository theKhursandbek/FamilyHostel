import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { TelegramProvider } from "./context/TelegramContext.jsx";
import { ThemeProvider } from "./theme/ThemeProvider.jsx";

import "./i18n";
import "./theme/tokens.css";
import "./index.css";
import { initSentry } from "./sentry.js";
import { initWebVitals } from "./webVitals.js";

initSentry();
initWebVitals();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <TelegramProvider>
          <ThemeProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
          </ThemeProvider>
        </TelegramProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
);

// PWA service worker — registered only on production builds (HTTPS or
// localhost). Inside Telegram WebView the registration is harmless and
// improves repeat-launch performance via cached shell.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Silent: SW is a progressive enhancement.
    });
  });
}
