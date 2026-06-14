/** Прокси /ymaps-v3/* → Яндекс Maps API (Referer = хост miniapp для Railway/Telegram). */
import { defineEventHandler, getRequestURL, proxyRequest } from "h3";

function yandexMapsKey(): string {
  return (
    process.env.VITE_YANDEX_MAPS_KEY?.trim() ||
    process.env.YANDEX_GEOCODER_KEY?.trim() ||
    ""
  );
}

export default defineEventHandler(async (event) => {
  const url = getRequestURL(event);
  const path = url.pathname.replace(/^\/ymaps-v3/, "/v3");
  const target = new URL(`https://api-maps.yandex.ru${path}`);
  url.searchParams.forEach((value, key) => {
    if (!target.searchParams.has(key)) target.searchParams.set(key, value);
  });
  if (!target.searchParams.has("lang")) target.searchParams.set("lang", "ru_RU");
  const key = yandexMapsKey();
  if (!target.searchParams.has("apikey") && key) target.searchParams.set("apikey", key);

  const proto =
    url.protocol === "http:" && !url.hostname.startsWith("localhost") ? "https" : url.protocol.replace(":", "");
  const referer = `${proto}://${url.host}`;

  return proxyRequest(event, target.toString(), {
    headers: {
      referer,
    },
  });
});
