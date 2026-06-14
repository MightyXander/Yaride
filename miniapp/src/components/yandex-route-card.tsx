import { useState } from "react";
import { Navigation } from "lucide-react";
import { Card } from "@/components/ui-kit";
import { openTripInYandexNavigator, tripHasRouteCoords } from "@/lib/yandex-navigator";
import { useTelegram } from "@/lib/telegram";

export type YandexRouteTarget = {
  fromTitle: string;
  toTitle: string;
  startLat?: number | null;
  startLng?: number | null;
  endLat?: number | null;
  endLng?: number | null;
};

export function YandexRouteCard({ target, className = "" }: { target: YandexRouteTarget; className?: string }) {
  const route = useYandexRouteOpen(target);
  if (!tripHasRouteCoords(target)) return null;

  return (
    <div className={className}>
      <Card onClick={route.loading ? undefined : route.open} className="!p-4">
        <div className="flex items-center gap-3">
          <div className="h-11 w-14 shrink-0 rounded-2xl brand-gradient grid place-items-center text-[#18170f]">
            <Navigation className="h-5 w-7" strokeWidth={2.25} />
          </div>
          <div className="min-w-0 text-left">
            <div className="font-semibold">{route.loading ? "Строим маршрут…" : "Маршрут в Яндекс"}</div>
          </div>
        </div>
      </Card>
      {route.error ? <p className="mt-2 text-xs text-destructive px-1">{route.error}</p> : null}
    </div>
  );
}

export function YandexRouteButton({
  target,
  className = "",
  disabled,
}: {
  target: YandexRouteTarget;
  className?: string;
  disabled?: boolean;
}) {
  const route = useYandexRouteOpen(target);
  if (!tripHasRouteCoords(target)) return null;

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => void route.open()}
        disabled={disabled || route.loading}
        className="w-full h-12 rounded-2xl bg-secondary text-secondary-foreground font-semibold press inline-flex items-center justify-center gap-2 disabled:opacity-50"
      >
        <Navigation className="size-5" />
        {route.loading ? "Открываем навигатор…" : "Маршрут в навигаторе"}
      </button>
      {route.error ? <p className="mt-2 text-xs text-destructive text-center">{route.error}</p> : null}
    </div>
  );
}

function useYandexRouteOpen(target: YandexRouteTarget) {
  const { haptic, openExternal } = useTelegram();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = async () => {
    if (!tripHasRouteCoords(target) || loading) return;
    setError(null);
    setLoading(true);
    haptic("light");
    try {
      await openTripInYandexNavigator(
        { lat: target.startLat, lng: target.startLng },
        { lat: target.endLat, lng: target.endLng },
        openExternal,
      );
      haptic("success");
    } catch (e) {
      haptic("error");
      setError(e instanceof Error ? e.message : "Не удалось открыть маршрут");
    } finally {
      setLoading(false);
    }
  };

  return { open, loading, error };
}
