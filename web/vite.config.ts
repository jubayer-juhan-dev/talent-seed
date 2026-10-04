import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// BASE: where the built app is served. "/next/" while it runs beside the current page (plan steps 2-6),
// "/" after the switch-over (step 7).
// Dev: `pnpm dev` proxies /api to the FastAPI server and adds the access key from TALENT_SEED_KEY.
export default defineConfig(({ mode }) => {
  const env = { ...process.env, ...loadEnv(mode, process.cwd(), "") };
  return {
    base: env.BASE ?? "/next/",
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
  };
});
