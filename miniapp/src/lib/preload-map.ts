import type { QueryClient } from "@tanstack/react-query";
import type { AnyRouter } from "@tanstack/react-router";

import { allStopsQueryOptions, districtsQueryOptions } from "./queries";
import { loadYmaps3React } from "./ymaps3";

const MAP_KEY = (import.meta.env.VITE_YANDEX_MAPS_KEY as string | undefined)?.trim() || undefined;

/** Каталог остановок + JS API 3.0 + lazy-чанки карты. */
export function preloadMapAssets(queryClient: QueryClient): void {
  void Promise.allSettled([
    queryClient.prefetchQuery(districtsQueryOptions()),
    queryClient.prefetchQuery(allStopsQueryOptions()),
  ]);

  void import("@/components/stop-map-picker");
  void import("@/components/stop-map-legacy");

  if (MAP_KEY) {
    void loadYmaps3React(MAP_KEY).catch(() => {
      /* на экране карты подключится API 2.1 */
    });
  }
}

/** Предзагрузка карты при старте поиска/создания поездки (данные + ymaps + чанк /route/map). */
export function preloadMapForRoutePick(router: AnyRouter, queryClient: QueryClient): void {
  preloadMapAssets(queryClient);
  void router.preloadRoute({ to: "/route/map" }).catch(() => {});
}
