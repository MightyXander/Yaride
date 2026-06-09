import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { refreshInitData } from "./init-data";
import { setInitDataProvider } from "./api";

type ThemeParams = Record<string, string>;

interface TgWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name: string; username?: string } };
  colorScheme: "light" | "dark";
  themeParams: ThemeParams;
  ready: () => void;
  expand: () => void;
  onEvent: (event: string, handler: () => void) => void;
  offEvent: (event: string, handler: () => void) => void;
  MainButton: {
    text: string;
    color?: string;
    textColor?: string;
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    setText: (text: string) => void;
    setParams: (p: { text?: string; color?: string; text_color?: string; is_active?: boolean; is_visible?: boolean }) => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
    selectionChanged: () => void;
  };
  openLink?: (url: string, options?: { try_instant_view?: boolean }) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
}

function isHttpUrl(url: string): boolean {
  try {
    const protocol = new URL(url).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

function openExternalUrl(url: string, webApp: TgWebApp | null) {
  if (!isHttpUrl(url)) {
    console.warn("[Yaride] Unsupported external URL scheme:", url);
    return;
  }
  if (webApp?.openLink) {
    webApp.openLink(url, { try_instant_view: false });
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

function getWebApp(): TgWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

const themeKeyMap: Record<string, string> = {
  bg_color: "--tg-bg",
  secondary_bg_color: "--tg-secondary-bg",
  text_color: "--tg-text",
  hint_color: "--tg-hint",
  link_color: "--tg-link",
  button_color: "--tg-button",
  button_text_color: "--tg-button-text",
  header_bg_color: "--tg-header-bg",
  section_bg_color: "--tg-section-bg",
  destructive_text_color: "--tg-destructive",
};

function applyTheme(params: ThemeParams) {
  const root = document.documentElement;
  for (const [tgKey, cssVar] of Object.entries(themeKeyMap)) {
    const v = params[tgKey];
    if (v) root.style.setProperty(cssVar, v);
  }
}

interface TelegramCtx {
  webApp: TgWebApp | null;
  isTelegram: boolean;
  user: { id: number; first_name: string; username?: string } | null;
  colorScheme: "light" | "dark";
  haptic: (type?: "light" | "medium" | "heavy" | "success" | "warning" | "error" | "selection") => void;
  openExternal: (url: string) => void;
}

const Ctx = createContext<TelegramCtx>({
  webApp: null,
  isTelegram: false,
  user: null,
  colorScheme: "light",
  haptic: () => {},
  openExternal: (url) => {
    if (typeof window !== "undefined") openExternalUrl(url, null);
  },
});

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [webApp, setWebApp] = useState<TgWebApp | null>(null);
  const [colorScheme, setColorScheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    let cancelled = false;
    const init = () => {
      const tg = getWebApp();
      if (!tg) {
        // Browser preview — theme controlled by ThemeProvider
        setColorScheme("dark");
        return;
      }
      try {
        tg.ready();
        tg.expand();
      } catch {}
      const realTelegram = !!tg.initData;
      const scheme = realTelegram ? tg.colorScheme : "dark";
      if (realTelegram) applyTheme(tg.themeParams ?? {});
      setColorScheme(scheme);
      setWebApp(tg);
      setInitDataProvider(refreshInitData);
      refreshInitData();

      const onTheme = () => {
        const fresh = getWebApp();
        if (!fresh) return;
        applyTheme(fresh.themeParams ?? {});
        setColorScheme(fresh.colorScheme);
      };
      tg.onEvent("themeChanged", onTheme);
      const onVisible = () => refreshInitData();
      tg.onEvent("viewportChanged", onVisible);
      return () => {
        tg.offEvent("themeChanged", onTheme);
        tg.offEvent("viewportChanged", onVisible);
      };
    };

    if (!window.Telegram?.WebApp) {
      const script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-web-app.js";
      script.async = true;
      script.onload = () => {
        if (cancelled) return;
        init();
      };
      document.head.appendChild(script);
      const cleanup = init();
      return () => {
        cancelled = true;
        cleanup?.();
      };
    }
    return init();
  }, []);


  const value: TelegramCtx = {
    webApp,
    isTelegram: !!webApp?.initData,
    user: webApp?.initDataUnsafe?.user ?? null,
    colorScheme,
    haptic: (type = "light") => {
      const h = webApp?.HapticFeedback;
      if (!h) return;
      if (type === "success" || type === "warning" || type === "error") {
        h.notificationOccurred(type);
      } else if (type === "selection") {
        h.selectionChanged();
      } else {
        h.impactOccurred(type);
      }
    },
    openExternal: (url: string) => {
      openExternalUrl(url, webApp);
    },
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTelegram() {
  return useContext(Ctx);
}

/** Hide Telegram MainButton (use with in-page BottomCTA `forceInPage`). */
export function useHideMainButton(active = true) {
  const { webApp } = useTelegram();
  useEffect(() => {
    if (!active) return;
    webApp?.MainButton?.hide();
  }, [webApp, active]);
}

/** Show Telegram MainButton with given text + handler. Falls back to in-page CTA. */
export function useMainButton(text: string, onClick: () => void, opts: { enabled?: boolean; visible?: boolean } = {}) {
  const { webApp } = useTelegram();
  const enabled = opts.enabled ?? true;
  const visible = opts.visible ?? true;

  useEffect(() => {
    const mb = webApp?.MainButton;
    if (!mb) return;
    mb.setParams({ text, is_active: enabled, is_visible: visible });
    const handler = () => {
      if (enabled) onClick();
    };
    mb.onClick(handler);
    if (visible) mb.show();
    else mb.hide();
    return () => {
      mb.offClick(handler);
      mb.hide();
    };
  }, [webApp, text, enabled, visible, onClick]);
}

/** Show Telegram BackButton with handler. */
export function useBackButton(onClick: (() => void) | null) {
  const { webApp } = useTelegram();
  useEffect(() => {
    const bb = webApp?.BackButton;
    if (!bb) return;
    if (!onClick) {
      bb.hide();
      return;
    }
    bb.onClick(onClick);
    bb.show();
    return () => {
      bb.offClick(onClick);
      bb.hide();
    };
  }, [webApp, onClick]);
}
