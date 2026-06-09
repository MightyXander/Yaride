/** URL загрузки JS API 3.0. В Telegram/WebView cross-origin Referer часто не доходит до Яндекса. */
export function ymaps3ScriptUrl(apiKey: string): string {
  const qs = `apikey=${encodeURIComponent(apiKey)}&lang=ru_RU`;

  if (typeof window === "undefined") {
    return `https://api-maps.yandex.ru/v3/?${qs}`;
  }

  const { hostname, origin } = window.location;
  const useSameOriginProxy =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname.endsWith(".trycloudflare.com");

  if (useSameOriginProxy) {
    return `${origin}/ymaps-v3/?${qs}`;
  }

  return `https://api-maps.yandex.ru/v3/?${qs}`;
}

export function ymaps3LoadDiagnostics() {
  if (typeof window === "undefined") {
    return { hostname: "", referrer: "", viaProxy: false };
  }
  const { hostname } = window.location;
  return {
    hostname,
    referrer: document.referrer || "(пусто)",
    viaProxy:
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname.endsWith(".trycloudflare.com"),
  };
}
