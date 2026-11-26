import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to its own origin and Vite passes /v1 on to the API, so the
// Turnstile cookie and the event stream are same-origin, as they are behind nginx in production.
const api = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8005";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/v1": { target: api, changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    css: false,
  },
});
