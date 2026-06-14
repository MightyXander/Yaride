/** Базовый URL API: build-time VITE_API_URL или runtime window.__YARIDE_API_URL__ (Railway). */

declare global {
  interface Window {
    __YARIDE_API_URL__?: string;
  }
}

export function apiBaseUrl(): string {
  const fromBuild = import.meta.env.VITE_API_URL?.trim();
  if (fromBuild) return fromBuild.replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const runtime = window.__YARIDE_API_URL__?.trim();
    if (runtime) return runtime.replace(/\/$/, "");
  }

  return "";
}

/** Для SSR shell: URL из env сервера miniapp (без trailing slash). */
export function serverApiBaseUrl(): string {
  const raw = process.env.API_URL?.trim() || process.env.VITE_API_URL?.trim() || "";
  return raw.replace(/\/$/, "");
}
