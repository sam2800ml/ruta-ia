import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El API vive en el mismo origen vía proxy: sin CORS en desarrollo.
// VITE_BASE se usa solo en el build de GitHub Pages (/<repo>/); en Docker y local queda "/".
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  server: { proxy: { "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") } } },
});
