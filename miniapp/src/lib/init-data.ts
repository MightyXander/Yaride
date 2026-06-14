/** Telegram WebApp initData: чтение, кэш сессии и ожидание готовности до API-запросов. */

const STORAGE_KEY = "yaride.tg.initData.v1";

function readFromHash(): string {
  if (typeof window === "undefined") return "";
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) return "";
  const params = new URLSearchParams(raw);
  const fromParam = params.get("tgWebAppData");
  if (fromParam) {
    try {
      return decodeURIComponent(fromParam);
    } catch {
      return fromParam;
    }
  }
  return "";
}

function readLive(): string {
  if (typeof window === "undefined") return "";
  return (window as any).Telegram?.WebApp?.initData ?? "";
}

function persist(value: string) {
  if (!value) return;
  try {
    sessionStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* ignore */
  }
}

/** Перечитать initData из WebApp, hash URL или sessionStorage (порядок приоритета). */
export function refreshInitData(): string {
  const live = readLive();
  if (live) {
    persist(live);
    return live;
  }
  const fromHash = readFromHash();
  if (fromHash) {
    persist(fromHash);
    return fromHash;
  }
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function getInitData(): string {
  return refreshInitData();
}

let bootstrapPromise: Promise<void> | null = null;

/** Ждём появления initData (или таймаут для dev-браузера без Telegram). */
export function bootstrapInitData(maxWaitMs = 5000): Promise<void> {
  if (bootstrapPromise) return bootstrapPromise;

  bootstrapPromise = new Promise((resolve) => {
    const started = Date.now();
    const attempt = () => {
      if (refreshInitData() || Date.now() - started >= maxWaitMs) {
        resolve();
        return;
      }
      window.setTimeout(attempt, 50);
    };
    attempt();
  });

  return bootstrapPromise;
}

/** Повторное ожидание initData (после 401 или возврата из фона). */
export async function waitForInitData(maxWaitMs = 2500): Promise<string> {
  const started = Date.now();
  while (Date.now() - started < maxWaitMs) {
    const value = refreshInitData();
    if (value) return value;
    await new Promise((r) => setTimeout(r, 50));
  }
  return refreshInitData();
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshInitData();
    }
  });
}
