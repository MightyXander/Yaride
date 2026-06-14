import { createFileRoute, Link, useNavigate, useRouter } from "@tanstack/react-router";
import {
  ArrowUpRight,
  Bell,
  Car,
  Clock,
  History,
  Plus,
  Search,
  Settings,
  Sparkles,
  Star,
  Ticket,
  UserRound,
} from "lucide-react";
import type * as React from "react";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Screen } from "@/components/ui-kit";
import { clearCreateWizardDraft } from "@/lib/create-wizard";
import { isActiveDriver, isDriverPending, isDriverRejected } from "@/lib/driver-access";
import { meQueryOptions } from "@/lib/queries";
import { useBackButton } from "@/lib/telegram";
import { preloadRoutePath, scheduleWarmApp } from "@/lib/warm-app";
import type { Role } from "@/lib/api";

export const Route = createFileRoute("/home")({
  component: Home,
});

type TileArt = (props: { className?: string }) => React.ReactElement;

const ArtSearch: TileArt = ({ className }) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} aria-hidden>
    <path d="M10 80 Q40 50 60 70 T110 50" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeDasharray="4 6" />
    <circle cx="60" cy="70" r="3" fill="currentColor" />
    <circle cx="98" cy="56" r="14" stroke="currentColor" strokeWidth="2.2" />
    <path d="M108 66 L116 74" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
  </svg>
);

const ArtCreate: TileArt = ({ className }) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} aria-hidden>
    <path d="M10 95 H110" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <rect x="34" y="58" width="58" height="30" rx="8" stroke="currentColor" strokeWidth="2.2" />
    <circle cx="48" cy="92" r="6" stroke="currentColor" strokeWidth="2.2" />
    <circle cx="82" cy="92" r="6" stroke="currentColor" strokeWidth="2.2" />
    <path d="M63 38 V52 M56 45 H70" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
  </svg>
);

const ArtBookings: TileArt = ({ className }) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} aria-hidden>
    <path d="M22 42 H86 a8 8 0 0 1 0 16 a6 6 0 0 0 0 12 a8 8 0 0 1 -8 8 H22 a8 8 0 0 1 -8 -8 a6 6 0 0 0 0 -12 a8 8 0 0 1 8 -16 Z" stroke="currentColor" strokeWidth="2.2" />
    <path d="M62 46 V82" stroke="currentColor" strokeWidth="2" strokeDasharray="3 4" />
    <circle cx="34" cy="64" r="3" fill="currentColor" />
  </svg>
);

const ArtManage: TileArt = ({ className }) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} aria-hidden>
    <rect x="18" y="36" width="84" height="44" rx="10" stroke="currentColor" strokeWidth="2.2" />
    <path d="M28 56 H50 M28 66 H44" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <circle cx="84" cy="62" r="8" stroke="currentColor" strokeWidth="2.2" />
    <path d="M84 54 V50 M84 74 V70 M92 62 H96 M72 62 H76" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const ArtFavorites: TileArt = ({ className }) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} aria-hidden>
    <path d="M60 38 l7 14 l16 2 l-12 11 l3 16 l-14 -8 l-14 8 l3 -16 l-12 -11 l16 -2 Z" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
    <path d="M14 92 H106" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 5" />
  </svg>
);

const ArtHistory: TileArt = ({ className }) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} aria-hidden>
    <circle cx="60" cy="60" r="28" stroke="currentColor" strokeWidth="2.2" />
    <path d="M60 44 V60 L72 68" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    <path d="M28 60 a32 32 0 0 1 8 -21 M32 32 V40 H40" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const TILES: {
  to: string;
  label: string;
  hint: string;
  icon: typeof Search;
  art: TileArt;
  roles: Role[];
  tone?: "brand" | "default";
  driverOnly?: boolean;
}[] = [
  { to: "/search", label: "Найти", hint: "поездку рядом", icon: Search, art: ArtSearch, roles: ["driver", "passenger"], tone: "brand" },
  { to: "/create", label: "Создать", hint: "новый рейс", icon: Plus, art: ArtCreate, roles: ["driver"], tone: "brand", driverOnly: true },
  { to: "/bookings", label: "Брони", hint: "активные места", icon: Ticket, art: ArtBookings, roles: ["driver", "passenger"] },
  { to: "/manage", label: "Мои рейсы", hint: "водительская", icon: Settings, art: ArtManage, roles: ["driver"], driverOnly: true },
  { to: "/favorites", label: "Избранное", hint: "маршруты", icon: Star, art: ArtFavorites, roles: ["driver", "passenger"] },
  { to: "/history", label: "История", hint: "архив поездок", icon: History, art: ArtHistory, roles: ["driver", "passenger"] },
];

function Home() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery(meQueryOptions());
  const navigate = useNavigate();
  const profile = data?.user ?? null;
  const registered = data?.registered ?? false;

  useBackButton(null);

  const activeDriver = profile ? isActiveDriver(profile) : false;

  useEffect(() => {
    if (!profile) return;
    return scheduleWarmApp(router, queryClient, { role: profile.role, activeDriver });
  }, [router, queryClient, profile, activeDriver]);

  const preload = (path: string) => {
    if (!profile) return;
    preloadRoutePath(router, queryClient, path, profile.role);
  };

  if (isLoading && !data) return <HomeSkeleton />;
  if (isError && !data) {
    return (
      <Screen>
        <SectionRetry onRetry={() => void refetch()} />
      </Screen>
    );
  }
  if (!registered || !profile) return <HomeEmpty onStart={() => navigate({ to: "/onboarding" })} />;

  const visible = TILES.filter((t) => {
    if (!t.roles.includes(profile.role)) return false;
    if (t.driverOnly && profile.role === "driver" && !activeDriver) return false;
    return true;
  });
  const isDriver = profile.role === "driver";
  const heroCta =
    isDriver && activeDriver
      ? { to: "/create", label: "Создать поездку" }
      : { to: "/search", label: "Найти поездку" };

  return (
    <Screen>
      {isDriverPending(profile) ? (
        <div className="mx-5 mt-4 rounded-2xl border border-brand/30 bg-brand/10 p-4 text-[13px]">
          <div className="font-semibold flex items-center gap-2">
            <Clock className="size-4" /> Заявка на модерации
          </div>
          <p className="text-muted-foreground mt-1">После одобления администратором вы сможете создавать поездки.</p>
        </div>
      ) : null}
      {isDriverRejected(profile) ? (
        <div className="mx-5 mt-4 rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-[13px]">
          <div className="font-semibold text-destructive">Заявка отклонена</div>
          <p className="text-muted-foreground mt-1">Обновите данные ВУ в профиле или обратитесь в поддержку.</p>
        </div>
      ) : null}

      <header className="px-5 pt-5 pb-2 flex items-center justify-between gap-3">
        <Link
          to="/account"
          preload="intent"
          onPointerDown={() => preload("/account")}
          className="flex items-center gap-3 active:opacity-70"
        >
          <div className="size-10 rounded-full brand-gradient grid place-items-center text-[15px] font-extrabold">
            {profile.name.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="text-[17px] font-bold leading-tight truncate">{profile.name}</div>
            <div className="text-[12px] text-muted-foreground flex items-center gap-1.5">
              <span className="size-1.5 rounded-full bg-brand" />
              {isDriver ? "Водитель" : "Пассажир"} · Ярославль
            </div>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <Link
            to="/notifications"
            preload="intent"
            onPointerDown={() => preload("/notifications")}
            aria-label="Уведомления"
            className="relative size-11 rounded-full bg-secondary text-secondary-foreground grid place-items-center active:opacity-70"
          >
            <Bell className="size-5" />
          </Link>
          <Link
            to="/account"
            preload="intent"
            onPointerDown={() => preload("/account")}
            aria-label="Аккаунт"
            className="size-11 rounded-full bg-secondary text-secondary-foreground grid place-items-center active:opacity-70"
          >
            <UserRound className="size-5" />
          </Link>
        </div>
      </header>

      <section className="px-5 mt-3">
        <Link
          to={heroCta.to}
          preload="intent"
          onPointerDown={() => preload(heroCta.to)}
          onClick={() => {
            if (heroCta.to === "/create") clearCreateWizardDraft();
          }}
          className="block relative overflow-hidden rounded-3xl brand-gradient brand-glow p-5 press-strong"
        >
          <div className="text-[11px] font-bold tracking-[0.18em] uppercase opacity-70">
            {isDriver && activeDriver ? "Поехали" : "Куда сегодня"}
          </div>
          <h2 className="mt-2 text-[30px] leading-[1.05] font-extrabold tracking-tight max-w-[80%]">
            {isDriver && activeDriver ? "Возьмите\nпопутчиков" : "Найдите\nпопутчика"}.
          </h2>
          <div className="mt-5 inline-flex items-center gap-2 h-11 px-4 rounded-full bg-[#18170f] text-white text-[14px] font-semibold">
            <Sparkles className="size-4" />
            {heroCta.label}
          </div>
        </Link>
      </section>

      <section className="px-5 mt-3 grid grid-cols-2 gap-3">
        <div className="surface-elevated p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Рейтинг</div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-[26px] font-extrabold leading-none">
              {profile.ratingCount ? profile.ratingAvg.toFixed(1) : "—"}
            </span>
            <Star size={16} className="fill-brand text-brand" strokeWidth={0} />
          </div>
          <div className="text-[12px] text-muted-foreground mt-1">
            {profile.ratingCount ? `${profile.ratingCount} оценок` : "пока без оценок"}
          </div>
        </div>
        <div className="surface-elevated p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Роль</div>
          <div className="mt-1 text-[20px] font-extrabold leading-tight">{isDriver ? "Водитель" : "Пассажир"}</div>
          <div className="text-[12px] text-muted-foreground mt-1 flex items-center gap-1">
            <Car className="size-3.5" />
            {isDriver ? (activeDriver ? "ВУ подтверждено" : "На модерации") : "Меняется в аккаунте"}
          </div>
        </div>
      </section>

      <section className="px-5 mt-4">
        <h3 className="text-[11px] uppercase tracking-[0.16em] font-bold text-muted-foreground px-1 mb-2.5">Что делаем</h3>
        <div className="grid grid-cols-2 gap-3 list-stagger">
          {visible.map((t) => {
            const Icon = t.icon;
            const Art = t.art;
            const isBrand = t.tone === "brand";
            return (
              <div key={t.to}>
                <Link
                  to={t.to}
                  preload="intent"
                  onPointerDown={() => preload(t.to)}
                  onClick={() => {
                    if (t.to === "/create") clearCreateWizardDraft();
                  }}
                  className={`relative rounded-3xl p-4 h-32 flex flex-col justify-between overflow-hidden press ${
                    isBrand ? "brand-gradient text-[#18170f]" : "surface-elevated"
                  }`}
                >
                  <Art className={`pointer-events-none absolute -right-3 -bottom-3 size-24 ${isBrand ? "text-black/15" : "text-foreground/10"}`} />
                  <div className={`relative size-11 rounded-2xl grid place-items-center ${isBrand ? "bg-black/10" : "bg-accent text-accent-foreground"}`}>
                    <Icon className="size-5" />
                  </div>
                  <div className="relative">
                    <div className="text-[18px] font-extrabold leading-tight">{t.label}</div>
                    <div className={`text-[12px] mt-0.5 ${isBrand ? "opacity-70" : "text-muted-foreground"}`}>{t.hint}</div>
                  </div>
                </Link>
              </div>
            );
          })}
        </div>
      </section>
    </Screen>
  );
}

function SectionRetry({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="px-5 pt-10 text-center">
      <p className="text-muted-foreground">Не удалось загрузить профиль</p>
      <button onClick={onRetry} className="mt-4 h-12 px-6 rounded-xl brand-gradient font-bold">
        Повторить
      </button>
    </div>
  );
}

function HomeSkeleton() {
  return (
    <Screen>
      <header className="px-5 pt-5 pb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-full bg-secondary animate-pulse" />
          <div className="space-y-2">
            <div className="h-4 w-28 rounded bg-secondary animate-pulse" />
            <div className="h-3 w-36 rounded bg-secondary animate-pulse" />
          </div>
        </div>
      </header>
      <section className="px-5 mt-3">
        <div className="h-44 rounded-3xl bg-secondary animate-pulse" />
      </section>
    </Screen>
  );
}

function HomeEmpty({ onStart }: { onStart: () => void }) {
  return (
    <Screen>
      <header className="px-5 pt-6">
        <h1 className="text-[30px] leading-[1.05] font-extrabold tracking-tight">Попутчики по городу — за минуту.</h1>
      </header>
      <section className="px-5 mt-6">
        <button onClick={onStart} className="w-full h-14 rounded-2xl brand-gradient text-[#18170f] text-[16px] font-extrabold press">
          Начать
        </button>
      </section>
    </Screen>
  );
}
