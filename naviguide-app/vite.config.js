import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Detect local development vs deployed environment
const isLocal = !process.env.VITE_DEPLOY_HOST;

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Split heavy dependencies into their own chunks so users don't pay the
    // parse cost of MapLibre / PMTiles on repeat visits (long-lived cache).
    rollupOptions: {
      output: {
        manualChunks: {
          maplibre: ["maplibre-gl", "@vis.gl/react-maplibre"],
          pmtiles:  ["pmtiles"],
          vendor:   ["react", "react-dom"],
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: ["j19hah46.run.complete.dev", "all"],
    proxy: {
      "/proxy": { target: "http://localhost:8000", changeOrigin: true },
    },
    // Local dev: use default HMR over localhost
    // Deployed: use WSS over production domain
    hmr: isLocal
      ? true
      : {
          protocol: "wss",
          host: "j19hah46.run.complete.dev",
          clientPort: 443,
        },
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: ["j19hah46.run.complete.dev", "all"],
  },
});
