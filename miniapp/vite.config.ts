// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, nitro (build-only using cloudflare as a default target),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import { loadEnv } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

/** Ключ JS API Яндекс.Карт: miniapp/.env → корень .env → YANDEX_GEOCODER_KEY. */
function resolveYandexMapsKey(mode = process.env.MODE || "development"): string {
  const miniappEnv = loadEnv(mode, __dirname, "VITE_");
  const rootEnv = loadEnv(mode, repoRoot, "");
  return (
    miniappEnv.VITE_YANDEX_MAPS_KEY?.trim() ||
    rootEnv.VITE_YANDEX_MAPS_KEY?.trim() ||
    rootEnv.YANDEX_GEOCODER_KEY?.trim() ||
    ""
  );
}

const yandexMapsKey = resolveYandexMapsKey();

export default defineConfig({
  nitro: {
    preset: "node-server",
    serverDir: "server",
  },
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    define: {
      "import.meta.env.VITE_YANDEX_MAPS_KEY": JSON.stringify(yandexMapsKey),
    },
    server: {
      port: Number(process.env.MINIAPP_PORT || 5174),
      strictPort: true,
      host: true,
      allowedHosts: [
        "localhost",
        "127.0.0.1",
        process.env.YARIDE_DEV_HOST || "yaride.local",
        ".yaride.local",
        ".trycloudflare.com",
      ],
      proxy: {
        "/api": { target: "http://127.0.0.1:8080", changeOrigin: true },
        "/health": { target: "http://127.0.0.1:8080", changeOrigin: true },
        // JS API 3.0: прокси с Referer = Host, иначе Telegram WebView режет cross-origin Referer.
        "/ymaps-v3": {
          target: "https://api-maps.yandex.ru",
          changeOrigin: true,
          secure: true,
          rewrite: (path) => path.replace(/^\/ymaps-v3/, "/v3"),
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyReq, req) => {
              const host = req.headers.host;
              if (typeof host === "string" && host) {
                const secure =
                  req.headers["x-forwarded-proto"] === "https" ||
                  (!host.startsWith("localhost") && !host.startsWith("127.0.0.1"));
                const scheme = secure ? "https" : "http";
                proxyReq.setHeader("Referer", `${scheme}://${host}/`);
              }

              // ymaps3 подгружает модули без ?lang= — Яндекс отвечает 400 без него.
              const rawPath = proxyReq.path || req.url || "";
              const parsed = new URL(rawPath, "http://ymaps-proxy.local");
              if (!parsed.searchParams.has("lang")) {
                parsed.searchParams.set("lang", "ru_RU");
              }
              if (!parsed.searchParams.has("apikey") && yandexMapsKey) {
                parsed.searchParams.set("apikey", yandexMapsKey);
              }
              proxyReq.path = `${parsed.pathname}${parsed.search}`;
            });
          },
        },
      },
    },
  },
});
