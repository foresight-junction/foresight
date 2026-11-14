import { defineConfig } from "vitest/config";

// Relative base so the built viewer works from any folder or static host.
export default defineConfig({
  base: "./",
  test: { environment: "node", passWithNoTests: true },
});
