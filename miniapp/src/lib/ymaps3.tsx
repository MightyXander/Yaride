import React, { useEffect, useState } from "react";
import * as ReactDOM from "react-dom";

import { ymaps3ScriptUrl } from "@/lib/ymaps3-script-url";

export type Ymaps3ReactApi = {
  YMap: React.ComponentType<Record<string, unknown>>;
  YMapDefaultSchemeLayer: React.ComponentType<Record<string, unknown>>;
  YMapDefaultFeaturesLayer: React.ComponentType<Record<string, unknown>>;
  YMapMarker: React.ComponentType<Record<string, unknown>>;
};

let loadPromise: Promise<Ymaps3ReactApi> | null = null;

function ensureYmaps3Script(apiKey: string): Promise<void> {
  if (window.ymaps3) return window.ymaps3.ready;

  const existing = document.querySelector<HTMLScriptElement>("script[data-yaride-ymaps3]");
  if (existing) {
    return new Promise((resolve, reject) => {
      const started = Date.now();
      const tick = () => {
        if (window.ymaps3) {
          window.ymaps3.ready.then(() => resolve()).catch(reject);
          return;
        }
        if (Date.now() - started > 20_000) {
          reject(new Error("Yandex Maps API v3 не ответил"));
          return;
        }
        window.setTimeout(tick, 100);
      };
      tick();
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = ymaps3ScriptUrl(apiKey);
    script.async = true;
    script.referrerPolicy = "strict-origin-when-cross-origin";
    script.dataset.yarideYmaps3 = "1";
    script.onload = () => {
      if (!window.ymaps3) {
        reject(new Error("Ключ отклонён или не поддерживает JavaScript API 3.0"));
        return;
      }
      window.ymaps3.ready.then(() => resolve()).catch(reject);
    };
    script.onerror = () => {
      reject(new Error("Не удалось загрузить Yandex Maps API v3"));
    };
    document.head.appendChild(script);
  });
}

export function resetYmaps3Loader() {
  loadPromise = null;
  document.querySelector('script[data-yaride-ymaps3]')?.remove();
}

export function loadYmaps3React(apiKey: string): Promise<Ymaps3ReactApi> {
  if (!loadPromise) {
    loadPromise = (async () => {
      try {
        await ensureYmaps3Script(apiKey);
        const ymaps3 = window.ymaps3;
        if (!ymaps3) {
          throw new Error("Yandex Maps API v3 недоступен");
        }

        await ymaps3.ready;
        const reactifyMod = (await ymaps3.import("@yandex/ymaps3-reactify")) as {
          reactify: {
            bindTo: (
              react: typeof React,
              reactDom: typeof ReactDOM,
            ) => {
              module: (pkg: typeof ymaps3) => Ymaps3ReactApi;
            };
          };
        };

        const reactify = reactifyMod.reactify.bindTo(React, ReactDOM);
        return reactify.module(ymaps3);
      } catch (error) {
        loadPromise = null;
        throw error;
      }
    })();
  }
  return loadPromise;
}

export function useYmaps3React(apiKey: string | undefined, retryKey = 0) {
  const [api, setApi] = useState<Ymaps3ReactApi | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!apiKey);

  useEffect(() => {
    if (!apiKey) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setApi(null);
    loadYmaps3React(apiKey)
      .then((loaded) => {
        if (!cancelled) {
          setApi(loaded);
          setLoading(false);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [apiKey, retryKey]);

  return { api, error, loading: !!apiKey && loading && !api && !error };
}
