import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В dev фронт проксирует /api и /health на локальный FastAPI (webapp_api), порт 8080.
// Так в коде используем относительные пути, без CORS-возни.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // слушать все интерфейсы — нужно для доступа с телефона / через туннель
    // Разрешаем любой хост: домены cloudflare/ngrok-туннелей меняются от запуска к запуску.
    // Это безопасно для локальной разработки (dev-сервер).
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: true },
      "/health": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
});
