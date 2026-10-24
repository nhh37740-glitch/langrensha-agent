import { defineConfig } from "vite";
export default defineConfig({
  build: {
    outDir: "../src/langrensha/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1800,
  },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
