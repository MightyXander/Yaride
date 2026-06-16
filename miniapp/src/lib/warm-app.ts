import type { QueryClient } from "@tanstack/react-query";
import type { AnyRouter } from "@tanstack/react-router";

import type { Role } from "./api";
import { preloadMapAssets, preloadMapForRoutePick } from "./preload-map";
import {
  bookingsQueryOptions,
  favoritesQueryOptions,
  historyQueryOptions,
  manageTripsQueryOptions,
  notificationsQueryOptions,
} from "./queries";

const MENU_PATHS = [
  "/search",
  "/create",
  "/bookings",
  "/manage",
  "/favorites",
  "/history",
  "/account",
  "/notifications",
] as const;

/** Routes already in the bundle or preloaded this session. */
const warmedRoutes = new Set<string>(["/", "/home"]);

let fullyWarmed = false;
let warmTask: Promise<void> | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

export function subscribeWarm(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function isRouteWarm(pathname: string) {
  return fullyWarmed || warmedRoutes.has(pathname);
}

export function isAppFullyWarmed() {
  return fullyWarmed;
}

function markWarm(path: string) {
  if (warmedRoutes.has(path)) return;
  warmedRoutes.add(path);
  notify();
}

/** Call when leaving a screen so the next visit can animate. */
export function markRouteVisited(pathname: string) {
  markWarm(pathname);
}

async function preloadRouteChunk(router: AnyRouter, path: string) {
  try {
    // TanStack Start splits route *components* into lazy chunks — preloadRoute loads them.
    await router.preloadRoute({ to: path as "/" });
    markWarm(path);
  } catch {
    markWarm(path);
  }
}

function prefetchRouteData(queryClient: QueryClient, path: string, role?: Role) {
  const tasks: Promise<unknown>[] = [];

  if (path === "/search" || path === "/create") {
    preloadMapAssets(queryClient);
    return Promise.resolve();
  }
  if (path === "/bookings") {
    tasks.push(queryClient.prefetchQuery(bookingsQueryOptions()));
  }
  if (path === "/manage" && role === "driver") {
    tasks.push(queryClient.prefetchQuery(manageTripsQueryOptions()));
  }
  if (path === "/favorites") {
    tasks.push(queryClient.prefetchQuery(favoritesQueryOptions()));
  }
  if (path === "/history" && role) {
    tasks.push(queryClient.prefetchQuery(historyQueryOptions(role)));
  }
  if (path === "/notifications") {
    tasks.push(queryClient.prefetchQuery(notificationsQueryOptions()));
  }

  return Promise.allSettled(tasks);
}

/** Preload one screen — call on pointerdown before navigation. */
export function preloadRoutePath(
  router: AnyRouter,
  queryClient: QueryClient,
  path: string,
  role?: Role,
) {
  markWarm(path);
  if (path === "/search" || path === "/create") {
    preloadMapForRoutePick(router, queryClient);
  }
  void Promise.allSettled([
    preloadRouteChunk(router, path),
    prefetchRouteData(queryClient, path, role),
  ]);
}

function menuPathsForRole(role: Role, activeDriver: boolean) {
  return MENU_PATHS.filter((path) => {
    if (path === "/create" || path === "/manage") {
      return role === "driver" && activeDriver;
    }
    return true;
  });
}

/** Background warm-up after home is shown — lazy chunks + API for the menu. */
export function startWarmApp(
  router: AnyRouter,
  queryClient: QueryClient,
  opts: { role: Role; activeDriver: boolean },
) {
  if (warmTask) return warmTask;

  warmTask = (async () => {
    // Прогреваем ассеты карты немедленно — не ждём перехода на /search или /create.
    preloadMapAssets(queryClient);

    const paths = menuPathsForRole(opts.role, opts.activeDriver);
    await Promise.allSettled(
      paths.flatMap((path) => [
        preloadRouteChunk(router, path),
        prefetchRouteData(queryClient, path, opts.role),
      ]),
    );
    // /route/map тянет ymaps — не прогреваем фоном, чтобы не ронять список районов.
    await Promise.allSettled([preloadRouteChunk(router, "/license")]);
    fullyWarmed = true;
    notify();
  })();

  return warmTask;
}

export function scheduleWarmApp(
  router: AnyRouter,
  queryClient: QueryClient,
  opts: { role: Role; activeDriver: boolean },
) {
  const run = () => startWarmApp(router, queryClient, opts);

  if (typeof requestIdleCallback !== "undefined") {
    const id = requestIdleCallback(run, { timeout: 3000 });
    return () => cancelIdleCallback(id);
  }

  const t = window.setTimeout(run, 300);
  return () => window.clearTimeout(t);
}
