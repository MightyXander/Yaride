import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { saveMapPick, mapPickToSearch, type MapPickFlow, type MapPickLeg } from "@/lib/map-pick";
import { useBackButton, useTelegram } from "@/lib/telegram";

const StopMapPicker = lazy(() =>
  import("@/components/stop-map-picker").then((m) => ({ default: m.StopMapPicker })),
);

type MapSearch = {
  leg: MapPickLeg;
  flow: MapPickFlow;
  fromPointId?: number;
  fromLabel?: string;
};

export const Route = createFileRoute("/route/map")({
  validateSearch: (search: Record<string, unknown>): MapSearch => ({
    leg: search.leg === "to" ? "to" : "from",
    flow: search.flow === "search" ? "search" : "create",
    fromPointId:
      typeof search.fromPointId === "number"
        ? search.fromPointId
        : search.fromPointId
          ? Number(search.fromPointId) || undefined
          : undefined,
    fromLabel: typeof search.fromLabel === "string" ? search.fromLabel : undefined,
  }),
  component: RouteMapScreen,
});

function RouteMapScreen() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { leg, flow, fromPointId, fromLabel } = Route.useSearch();

  const title = leg === "from" ? "Точка посадки" : "Точка высадки";
  const subtitle =
    leg === "to" && fromLabel ? `Старт: ${fromLabel}` : "Только остановки из каталога Yaride";

  useBackButton(() => {
    haptic("light");
    navigate({ to: flow === "create" ? "/create" : "/search" });
  });

  return (
    <Suspense fallback={<div className="fixed inset-0 grid place-items-center bg-background">Загрузка карты…</div>}>
      <StopMapPicker
        title={title}
        subtitle={subtitle}
        onListFallback={() => navigate({ to: flow === "create" ? "/create" : "/search" })}
        onConfirm={(stop) => {
          haptic("success");
          const payload = {
            flow,
            leg,
            pointId: stop.id,
            label: stop.title,
            fromPointId,
            fromLabel,
          };
          saveMapPick(payload);
          navigate({
            to: flow === "create" ? "/create" : "/search",
            search: mapPickToSearch(payload),
          });
        }}
      />
    </Suspense>
  );
}
