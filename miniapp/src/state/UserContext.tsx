import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type MeResponse } from "../api/client";

interface UserContextValue {
  me: MeResponse | null;
  loading: boolean;
  error: string | null;
  /** silent: true — обновить профиль без полноэкранного LoadingView (после локальных действий). */
  refresh: (options?: { silent?: boolean }) => Promise<void>;
}

const UserContext = createContext<UserContextValue | null>(null);

// Загружает /me один раз при старте; даёт доступ к профилю и признаку регистрации всем экранам.
export function UserProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      setMe(await api.me());
    } catch (e) {
      if (!silent) {
        setError(e instanceof Error ? e.message : "Ошибка авторизации");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return <UserContext.Provider value={{ me, loading, error, refresh }}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
