import type { QueryClient } from "@tanstack/react-query";
import type { AnyRouter } from "@tanstack/react-router";

import { allStopsQueryOptions, districtsQueryOptions } from "./queries";

/** Каталог остановок + lazy-чанк карты (Leaflet). */
export function preloadMapAssets(queryClient: QueryClient): void {
  void Promise.allSettled([
    queryClient.prefetchQuery(districtsQueryOptions()),
    queryClient.prefetchQuery(allStopsQueryOptions()),
  ]);
  void import("@/components/stop-map-picker");
}

/** Предзагрузка карты при старте поиска/создания поездки. */
export function preloadMapForRoutePick(router: AnyRouter, queryClient: QueryClient): void {
  preloadMapAssets(queryClient);
  void router.preloadRoute({ to: "/route/map" }).catch(() => {});
}
