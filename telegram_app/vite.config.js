import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Telegram Mini App dev server.
// Telegram Web requires HTTPS in production, but local dev uses http://localhost.
// Run: npm run dev (port 5174 by default, separate from the admin panel on 5173)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: true,
  },
});
