import { defineConfig } from "vite";

// BASE_PATH lets the same build serve from a domain root or a GitHub Pages subpath.
export default defineConfig({
  base: process.env.BASE_PATH ?? "/",
  build: { target: "es2020", cssCodeSplit: false, assetsInlineLimit: 0 },
});
