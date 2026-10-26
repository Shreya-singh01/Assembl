import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// In development the API and Socket.IO are proxied, so the browser talks to a
// single origin and the session cookie can stay SameSite=Lax.
const backend = process.env.VITE_DEV_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      "/socket.io": { target: backend, ws: true, changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
