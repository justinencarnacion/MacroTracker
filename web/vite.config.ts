import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages serves this repo's site at /MacroTracker/.
export default defineConfig({
  plugins: [react()],
  base: "/MacroTracker/",
});
