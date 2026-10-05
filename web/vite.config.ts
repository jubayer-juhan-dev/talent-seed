/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// BASE: where the built app is served (default "/"; override with BASE=/sub/path/ to host it elsewhere).
// Dev: `pnpm dev` proxies /api to the FastAPI server and adds the access key from TALENT_SEED_KEY.
export default defineConfig(({ mode }) => {
  const env = { ...process.env, ...loadEnv(mode, process.cwd(), "") };
  return {
    base: env.BASE ?? "/",
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.resolve(__dirname, "src") } },
    server: {
      host: "127.0.0.1",
      proxy: {
        "/api": {
          target: env.API_URL ?? "http://127.0.0.1:8765",
          headers: env.TALENT_SEED_KEY ? { "X-Access-Key": env.TALENT_SEED_KEY } : {},
        },
      },
    },
    build: { chunkSizeWarningLimit: 900 },
    // Unit tests only; e2e/ is Playwright's.
    test: { include: ["src/**/*.test.ts"] },
  };
});
