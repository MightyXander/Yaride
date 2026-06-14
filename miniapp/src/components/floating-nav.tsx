import { useRouter, useRouterState } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { CarFront, Search, UserRound } from "lucide-react";
import { createPortal } from "react-dom";
import { markNavTabSwitch, navTabForPath, type NavTabRoot } from "@/lib/nav-tabs";
import { preloadRoutePath } from "@/lib/warm-app";
import { useTelegram } from "@/lib/telegram";

type NavItem = {
  to: NavTabRoot;
  label: string;
  Icon: typeof Search;
};

const ITEMS: NavItem[] = [
  { to: "/search", label: "Поиск", Icon: Search },
  { to: "/home", label: "Поездки", Icon: CarFront },
  { to: "/account", label: "Профиль", Icon: UserRound },
];

const HIDDEN_ON = ["/onboarding", "/rate", "/route/map"];

/** Высота pill без внешних отступов (h-[3.75rem]). */
export const FLOATING_NAV_HEIGHT = "3.75rem";

/** Отступ для fixed CTA над pill-навигацией (синхронно с style nav ниже). */
export const FLOATING_NAV_BOTTOM = "14px";
export const BOTTOM_CTA_ABOVE_FLOATING_NAV = `calc(${FLOATING_NAV_BOTTOM} + env(safe-area-inset-bottom, 0px) + ${FLOATING_NAV_HEIGHT} + 10px)`;

function FloatingNavBar({ activeTab }: { activeTab: NavTabRoot }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const current = ITEMS.findIndex(({ to }) => to === activeTab);

  return (
    <div className="floating-nav-root pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center overflow-hidden pb-[max(14px,env(safe-area-inset-bottom,0px))] pt-3">
      <div className="w-[20rem] max-w-[calc(100%-2rem)]">
      <nav
        aria-label="Основная навигация"
        data-no-tap-glow
        className="pointer-events-auto relative grid h-[3.75rem] w-full grid-cols-3 gap-1 overflow-visible rounded-full border border-border/60 bg-card/95 p-1.5 shadow-floating-nav backdrop-blur-xl"
      >
        <div
          aria-hidden
          className="floating-nav-indicator pointer-events-none absolute top-1.5 bottom-1.5 left-1.5 rounded-full brand-gradient shadow-[0_4px_14px_-4px_rgba(255,210,40,0.55)]"
          style={{
            width: "calc((100% - 0.75rem - 0.5rem) / 3)",
            transform: `translateX(calc(${current} * (100% + 0.25rem)))`,
          }}
        />
        {ITEMS.map(({ to, label, Icon }, index) => {
          const active = index === current;
          return (
            <button
              key={to}
              type="button"
              aria-label={label}
              aria-current={active ? "page" : undefined}
              title={label}
              data-no-tap-glow
              onPointerDown={() => {
                markNavTabSwitch(to);
                preloadRoutePath(router, queryClient, to);
                haptic(active ? "light" : "selection");
              }}
              onClick={() => {
                if (active) {
                  haptic("light");
                  return;
                }
                void router.navigate({ to });
              }}
              className="relative z-10 flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-full touch-manipulation select-none"
            >
              <Icon
                className={`relative z-10 size-[18px] shrink-0 transition-colors duration-200 ${
                  active ? "text-[#18170f]" : "text-muted-foreground"
                }`}
                strokeWidth={2}
                aria-hidden
              />
              <span
                className={`h-3 max-w-full truncate px-0.5 text-[10px] font-semibold leading-none transition-opacity duration-200 ${
                  active ? "opacity-100 text-[#18170f]" : "opacity-0"
                }`}
                aria-hidden={!active}
              >
                {label}
              </span>
            </button>
          );
        })}
      </nav>
      </div>
    </div>
  );
}

export function FloatingNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const activeTab = navTabForPath(pathname);

  if (HIDDEN_ON.some((p) => pathname.startsWith(p))) return null;
  if (!activeTab) return null;
  if (typeof document === "undefined") return null;

  return createPortal(<FloatingNavBar activeTab={activeTab} />, document.body);
}
