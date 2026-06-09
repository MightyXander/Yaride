export type ResolvedTheme = "light" | "dark";

export function refererHostnames(hostname: string) {
  const lines = [hostname, "trycloudflare.com", "web.telegram.org", "localhost", "127.0.0.1"].filter(
    Boolean,
  );
  return [...new Set(lines)];
}

export function mapRefererShort(hostname: string) {
  if (!hostname) {
    return "Добавьте домен mini app в HTTP Referer ключа Яндекс.Карт (без https://).";
  }
  return `Добавьте «${hostname}» в HTTP Referer ключа Яндекс.Карт (без https://).`;
}

export function mapRefererHelp(hostname: string) {
  const lines = refererHostnames(hostname).join("\n");
  return `Ключ → «Ограничение по HTTP Referer» (без https://, по одному на строку):\n${lines}\n\n«trycloudflare.com» покрывает любой новый tunnel *.trycloudflare.com.\n«web.telegram.org» — если Telegram подставляет свой Referer.\n\nУбедитесь, что ключ для JavaScript API 3.0. После сохранения подождите до 15 минут.`;
}