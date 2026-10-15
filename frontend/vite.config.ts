// @lovable.dev/vite-tanstack-config already includes core plugins — do NOT add them manually.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      proxy: {
        "/api": { target: "http://localhost:8000", changeOrigin: true },
        "/media": { target: "http://localhost:8000", changeOrigin: true },
      },
    },
  },
});
