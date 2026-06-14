/** Прокси /api/* → yaride-core (runtime API_URL на сервисе miniapp). */
import { createError, defineEventHandler, proxyRequest } from "h3";

function upstreamBase(): string {
  return (process.env.API_URL?.trim() || process.env.VITE_API_URL?.trim() || "").replace(/\/$/, "");
}

export default defineEventHandler(async (event) => {
  const base = upstreamBase();
  if (!base) {
    throw createError({
      statusCode: 502,
      statusMessage: "API_URL не задан на сервисе yaride-miniapp.",
    });
  }
  return proxyRequest(event, `${base}${event.path}`);
});
