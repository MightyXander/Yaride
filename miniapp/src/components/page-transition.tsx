import { AnimatePresence, motion, useIsPresent } from "framer-motion";
import { useRouterState } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { isRouteWarm, markRouteVisited, subscribeWarm } from "@/lib/warm-app";
import { isNavTabSwitch, takePendingNavTabSwitch } from "@/lib/nav-tabs";

const PAGE_LEAVE_MS = 240;

function useRouteWarm(pathname: string) {
  return useSyncExternalStore(
    subscribeWarm,
    () => isRouteWarm(pathname),
    () => true,
  );
}

export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const prevPathRef = useRef(pathname);
  const from = prevPathRef.current;
  const instantTabSwitch =
    takePendingNavTabSwitch(pathname) || isNavTabSwitch(from, pathname);

  useLayoutEffect(() => {
    prevPathRef.current = pathname;
    if (instantTabSwitch) {
      document.documentElement.dataset.navSwitch = "";
      return () => {
        delete document.documentElement.dataset.navSwitch;
      };
    }
    delete document.documentElement.dataset.navSwitch;
  }, [pathname, instantTabSwitch]);

  useLayoutEffect(() => {
    document.documentElement.scrollLeft = 0;
    document.body.scrollLeft = 0;
    window.scrollTo({ top: window.scrollY, left: 0 });
  }, [pathname]);

  return (
    <>
      <div className="page-transition-root relative min-h-dvh bg-background">
        <AnimatePresence initial={false}>
          <PageLayer key={pathname} routePath={pathname} instant={instantTabSwitch}>
            {children}
          </PageLayer>
        </AnimatePresence>
      </div>
      <TapBurstLayer />
    </>
  );
}

function PageLayer({
  children,
  routePath,
  instant,
}: {
  children: ReactNode;
  routePath: string;
  instant: boolean;
}) {
  const isPresent = useIsPresent();
  const warm = useRouteWarm(routePath);

  // Mark ready for animation on the *next* visit (after this screen has loaded once).
  useEffect(() => {
    return () => markRouteVisited(routePath);
  }, [routePath]);

  const animClass = instant ? "" : !isPresent ? "page-leave" : warm ? "page-enter" : "";

  return (
    <motion.div
      initial={false}
      className={`page-shell min-h-dvh w-full bg-background ${animClass}`}
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: isPresent ? "auto" : "none",
      }}
      exit={{ transition: { duration: PAGE_LEAVE_MS / 1000 } }}
    >
      {children}
    </motion.div>
  );
}

function TapBurstLayer() {
  const [bursts, setBursts] = useState<{ id: number; x: number; y: number }[]>([]);
  const counter = useRef(0);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const hit = target.closest<HTMLElement>("button, [role=\"button\"]");
      if (!hit) return;
      if (hit.hasAttribute("data-no-tap-glow")) return;

      const id = ++counter.current;
      setBursts((b) => [...b, { id, x: e.clientX, y: e.clientY }]);
      window.setTimeout(() => {
        setBursts((b) => b.filter((it) => it.id !== id));
      }, 650);
    }

    window.addEventListener("pointerdown", onPointerDown, { passive: true });
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, []);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-[9998] overflow-hidden">
      {bursts.map((b) => (
        <span
          key={b.id}
          className="tap-burst"
          style={{ left: b.x, top: b.y }}
        />
      ))}
    </div>
  );
}
