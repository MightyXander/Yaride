import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemeMode = "system" | "light" | "dark";
const KEY = "yaride.theme.v1";

interface ThemeCtx {
  mode: ThemeMode;
  resolved: "light" | "dark";
  setMode: (m: ThemeMode) => void;
}

const Ctx = createContext<ThemeCtx>({
  mode: "system",
  resolved: "dark",
  setMode: () => {},
});

function readStored(): ThemeMode {
  if (typeof window === "undefined") return "system";
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {}
  return "system";
}

function applyClass(resolved: "light" | "dark") {
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.dataset.theme = resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("dark");

  useEffect(() => {
    setModeState(readStored());
  }, []);

  useEffect(() => {
    function resolve(m: ThemeMode): "light" | "dark" {
      if (m !== "system") return m;
      const tg = (window as any).Telegram?.WebApp?.colorScheme;
      if (tg === "light" || tg === "dark") return tg;
      if (window.matchMedia?.("(prefers-color-scheme: light)").matches) return "light";
      return "dark";
    }
    const r = resolve(mode);
    setResolved(r);
    applyClass(r);

    if (mode !== "system") return;
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const handler = () => {
      const next = resolve("system");
      setResolved(next);
      applyClass(next);
    };
    mq?.addEventListener?.("change", handler);
    return () => mq?.removeEventListener?.("change", handler);
  }, [mode]);

  const setMode = (m: ThemeMode) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {}
  };

  return <Ctx.Provider value={{ mode, resolved, setMode }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  return useContext(Ctx);
}
