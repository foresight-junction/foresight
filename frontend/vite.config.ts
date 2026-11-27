import { defineConfig } from "vitest/config";

// Relative base so the built viewer works from any folder or static host.
// /live goes to the live-episode server (frontend/tools/live, its default --port 8770) for ?live=1.
export default defineConfig({
  base: "./",
  build: { rollupOptions: { input: ["index.html", "walkthrough.html"] } },
  server: {
    proxy: { "/live": { target: "http://127.0.0.1:8770", changeOrigin: true } },
  },
  test: { environment: "node", passWithNoTests: true },
});
