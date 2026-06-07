// Тонкая типизированная обёртка над window.Telegram.WebApp.
// Используем нативный Web App API (а не SDK-пакеты): он стабилен, сам прокидывает
// --tg-theme-* переменные и не тянет deprecated-зависимости.

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: TelegramUser };
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  isExpanded: boolean;
  ready: () => void;
  expand: () => void;
  close: () => void;
  MainButton: {
    text: string;
    isVisible: boolean;
    isActive: boolean;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    setText: (text: string) => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
  };
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
    selectionChanged: () => void;
  };
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

// Признак запуска внутри Telegram (есть initData). В обычном браузере — false.
export function isTelegramEnv(): boolean {
  const wa = getWebApp();
  return Boolean(wa && wa.initData);
}

// Применяет тему Telegram к <html>: класс dark/light для Tailwind darkMode: 'class'.
export function applyTelegramTheme(): void {
  const wa = getWebApp();
  const scheme = wa?.colorScheme ?? "light";
  const root = document.documentElement;
  root.classList.toggle("dark", scheme === "dark");
}

// Инициализация при старте приложения.
export function initTelegram(): void {
  const wa = getWebApp();
  if (!wa) return;
  wa.ready();
  wa.expand();
  applyTelegramTheme();
}

export function haptic(style: "light" | "medium" | "heavy" = "light"): void {
  getWebApp()?.HapticFeedback?.impactOccurred(style);
}
