import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to its own origin and Vite passes /v1 on to the API, so the
// Turnstile cookie and the event stream are same-origin, as they are behind nginx in production.
const api = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8005";

// The avatar page and its Unity build live in the repo's avatar/ folder, which nginx serves at
// /avatar/ in production. This serves it the same way in development and preview.
const AVATAR = resolve(import.meta.dirname, "../avatar");
const TYPES = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".json": "application/json",
  ".wasm": "application/wasm",
  ".data": "application/octet-stream",
};

function serveAvatar() {
  const middleware = (req, res, next) => {
    const path = decodeURIComponent((req.url || "").split("?")[0]);
    if (!path.startsWith("/avatar/")) return next();
    const file = normalize(join(AVATAR, path.slice("/avatar/".length) || "index.html"));
    const target = existsSync(file) && statSync(file).isDirectory() ? join(file, "index.html") : file;
    if (!target.startsWith(AVATAR) || !existsSync(target)) {
      res.statusCode = 404;
      return res.end();
    }
    res.setHeader("Content-Type", TYPES[extname(target)] || "application/octet-stream");
    res.setHeader("Cache-Control", "no-cache");
    createReadStream(target).pipe(res);
  };
  return {
    name: "serve-avatar",
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}

export default defineConfig({
  plugins: [react(), serveAvatar()],
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
