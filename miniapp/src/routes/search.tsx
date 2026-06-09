import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, MapPin, Search as SearchIcon } from "lucide-react";
import {
  EmptyState,
  Screen,
  ScreenHeader,
  Section,
  TripCard,
  formatTripDate,
} from "@/components/ui-kit";
import { DistrictStep, GeoStep, RouteDateStep, StopStep } from "@/components/route-pick-steps";
import {
  EMPTY_SEARCH_FILTERS,
  FilterButton,
  SearchFilterSheet,
  searchFiltersActive,
  type SearchTripFilters,
} from "@/components/search-filter-sheet";
import { api, type ApiTrip } from "@/lib/api";
import { apiTripToCard } from "@/lib/adapters";
import {
  hasMapPickSearch,
  parseMapPickSearch,
  parseOptionalInt,
  readPendingMapPick,
} from "@/lib/map-pick";
import { districtsQueryOptions, queryKeys } from "@/lib/queries";
import { saveDistrictRoute } from "@/lib/saved-district-route";
import { preloadMapForRoutePick } from "@/lib/preload-map";
import { useBackButton, useTelegram } from "@/lib/telegram";

export type SearchRouteSearch = ReturnType<typeof parseSearchRouteSearch>;

function parseSearchRouteSearch(search: Record<string, unknown>) {
  return {
    ...parseMapPickSearch(search),
    fromPointId: parseOptionalInt(search.fromPointId),
    toPointId: parseOptionalInt(search.toPointId),
    fromLabel: typeof search.fromLabel === "string" ? search.fromLabel : undefined,
    toLabel: typeof search.toLabel === "string" ? search.toLabel : undefined,
  };
}

export const Route = createFileRoute("/search")({
  validateSearch: parseSearchRouteSearch,
  component: SearchScreen,
});

type Phase =
  | { kind: "from-district" }
  | { kind: "from-stop"; district: string }
  | { kind: "from-geo" }
  | {
      kind: "to-district";
      fromPointId: number;
      fromLabel: string;
      fromDistrict?: string;
    }
  | {
      kind: "to-stop";
      fromPointId: number;
      fromLabel: string;
      fromDistrict?: string;
      district: string;
    }
  | {
      kind: "date";
      fromPointId: number;
      toPointId: number;
      fromLabel: string;
      toLabel: string;
      fromDistrict?: string;
      toDistrict?: string;
    }
  | {
      kind: "results";
      mode: "exact" | "district";
      fromPointId: number;
      toPointId: number;
      fromLabel: string;
      toLabel: string;
      fromDistrict?: string;
      toDistrict?: string;
      date: string;
    };

function sortTripsByTime(trips: ApiTrip[]): ApiTrip[] {
  return [...trips].sort((a, b) => {
    const ta = a.departureTime ?? "";
    const tb = b.departureTime ?? "";
    if (ta !== tb) return ta.localeCompare(tb);
    return a.id - b.id;
  });
}

function applyTripFilters(trips: ApiTrip[], filters: SearchTripFilters): ApiTrip[] {
  return trips.filter((t) => {
    if (filters.departureTime && t.departureTime !== filters.departureTime) return false;
    if (filters.minSeatsFree != null && t.seatsFree < filters.minSeatsFree) return false;
    return true;
  });
}

function SearchScreen() {
  const navigate = useNavigate();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const mapSearch = Route.useSearch();
  const [phase, setPhase] = useState<Phase>({ kind: "from-district" });
  const routePrefillHandled = useRef(false);

  useEffect(() => {
    preloadMapForRoutePick(router, queryClient);
  }, [router, queryClient]);

  useEffect(() => {
    if (routePrefillHandled.current) return;
    const { fromPointId, toPointId, fromLabel, toLabel } = mapSearch;
    if (!fromPointId || !toPointId || !fromLabel || !toLabel) return;
    routePrefillHandled.current = true;
    setPhase({
      kind: "date",
      fromPointId,
      toPointId,
      fromLabel,
      toLabel,
    });
    navigate({ to: "/search", search: {}, replace: true });
  }, [mapSearch.fromPointId, mapSearch.toPointId, mapSearch.fromLabel, mapSearch.toLabel, navigate]);

  useEffect(() => {
    const pick = readPendingMapPick("search", mapSearch);
    if (!pick || pick.flow !== "search") return;

    if (pick.leg === "from") {
      setPhase({ kind: "to-district", fromPointId: pick.pointId, fromLabel: pick.label });
    } else if (pick.fromPointId != null && pick.fromLabel) {
      setPhase({
        kind: "date",
        fromPointId: pick.fromPointId,
        fromLabel: pick.fromLabel,
        toPointId: pick.pointId,
        toLabel: pick.label,
      });
    }

    if (hasMapPickSearch(mapSearch)) {
      navigate({ to: "/search", search: {}, replace: true });
    }
  }, [
    mapSearch.mpLeg,
    mapSearch.mpId,
    mapSearch.mpLabel,
    mapSearch.mpFromId,
    mapSearch.mpFromLabel,
    navigate,
  ]);

  const openMap = (leg: "from" | "to", ctx?: { fromPointId: number; fromLabel: string; fromDistrict?: string }) => {
    haptic("light");
    navigate({
      to: "/route/map",
      search: {
        leg,
        flow: "search",
        ...(ctx ? { fromPointId: ctx.fromPointId, fromLabel: ctx.fromLabel } : {}),
      },
    });
  };

  const districtsQ = useQuery(districtsQueryOptions());

  useBackButton(() => {
    haptic("light");
    if (phase.kind === "from-district") navigate({ to: "/home" });
    else if (phase.kind === "from-stop") setPhase({ kind: "from-district" });
    else if (phase.kind === "from-geo") setPhase({ kind: "from-district" });
    else if (phase.kind === "to-district") setPhase({ kind: "from-district" });
    else if (phase.kind === "to-stop")
      setPhase({
        kind: "to-district",
        fromPointId: phase.fromPointId,
        fromLabel: phase.fromLabel,
        fromDistrict: phase.fromDistrict,
      });
    else if (phase.kind === "date")
      setPhase({
        kind: "to-district",
        fromPointId: phase.fromPointId,
        fromLabel: phase.fromLabel,
        fromDistrict: phase.fromDistrict,
      });
    else if (phase.kind === "results")
      setPhase({
        kind: "date",
        fromPointId: phase.fromPointId,
        toPointId: phase.toPointId,
        fromLabel: phase.fromLabel,
        toLabel: phase.toLabel,
        fromDistrict: phase.fromDistrict,
        toDistrict: phase.toDistrict,
      });
  });

  return (
    <Screen>
      {phase.kind === "from-district" && (
        <DistrictStep
          title="Откуда едем"
          subtitle="Выбери район посадки"
          districts={districtsQ.data?.districts ?? []}
          loading={districtsQ.isLoading}
          showGeo
          onMap={() => openMap("from")}
          onGeo={() => setPhase({ kind: "from-geo" })}
          onPick={(d) => setPhase({ kind: "from-stop", district: d })}
          crumbs={["Ярославль"]}
        />
      )}

      {phase.kind === "from-stop" && (
        <StopStep
          district={phase.district}
          title="Остановка посадки"
          crumbs={["Ярославль", phase.district]}
          onPick={(id, label) =>
            setPhase({
              kind: "to-district",
              fromPointId: id,
              fromLabel: label,
              fromDistrict: phase.district,
            })
          }
        />
      )}

      {phase.kind === "from-geo" && (
        <GeoStep
          onPick={(id, label) => setPhase({ kind: "to-district", fromPointId: id, fromLabel: label })}
          onManual={() => setPhase({ kind: "from-district" })}
        />
      )}

      {phase.kind === "to-district" && (
        <DistrictStep
          title="Куда едем"
          subtitle="Выбери район высадки"
          districts={districtsQ.data?.districts ?? []}
          loading={districtsQ.isLoading}
          onMap={() =>
            openMap("to", {
              fromPointId: phase.fromPointId,
              fromLabel: phase.fromLabel,
              fromDistrict: phase.fromDistrict,
            })
          }
          onPick={(d) =>
            setPhase({
              kind: "to-stop",
              fromPointId: phase.fromPointId,
              fromLabel: phase.fromLabel,
              fromDistrict: phase.fromDistrict,
              district: d,
            })
          }
          crumbs={["Ярославль", phase.fromLabel, "→"]}
        />
      )}

      {phase.kind === "to-stop" && (
        <StopStep
          district={phase.district}
          title="Остановка высадки"
          crumbs={["Ярославль", phase.district]}
          onPick={(id, label) =>
            setPhase({
              kind: "date",
              fromPointId: phase.fromPointId,
              toPointId: id,
              fromLabel: phase.fromLabel,
              toLabel: label,
              fromDistrict: phase.fromDistrict,
              toDistrict: phase.district,
            })
          }
        />
      )}

      {phase.kind === "date" && (
        <RouteDateStep
          onPick={(date) =>
            setPhase({
              kind: "results",
              mode: "exact",
              fromPointId: phase.fromPointId,
              toPointId: phase.toPointId,
              fromLabel: phase.fromLabel,
              toLabel: phase.toLabel,
              fromDistrict: phase.fromDistrict,
              toDistrict: phase.toDistrict,
              date,
            })
          }
        />
      )}

      {phase.kind === "results" && (
        <Results
          mode={phase.mode}
          fromPointId={phase.fromPointId}
          toPointId={phase.toPointId}
          fromLabel={phase.fromLabel}
          toLabel={phase.toLabel}
          fromDistrict={phase.fromDistrict}
          toDistrict={phase.toDistrict}
          date={phase.date}
          onChangeDate={() =>
            setPhase({
              kind: "date",
              fromPointId: phase.fromPointId,
              toPointId: phase.toPointId,
              fromLabel: phase.fromLabel,
              toLabel: phase.toLabel,
              fromDistrict: phase.fromDistrict,
              toDistrict: phase.toDistrict,
            })
          }
          onSwitchToDistrict={(startDistrict, endDistrict) => {
            saveDistrictRoute(startDistrict, endDistrict);
            haptic("light");
            setPhase({
              ...phase,
              mode: "district",
              fromDistrict: startDistrict,
              toDistrict: endDistrict,
            });
          }}
        />
      )}
    </Screen>
  );
}

function Results({
  mode,
  fromPointId,
  toPointId,
  fromLabel,
  toLabel,
  fromDistrict,
  toDistrict,
  date,
  onChangeDate,
  onSwitchToDistrict,
}: {
  mode: "exact" | "district";
  fromPointId: number;
  toPointId: number;
  fromLabel: string;
  toLabel: string;
  fromDistrict?: string;
  toDistrict?: string;
  date: string;
  onChangeDate: () => void;
  onSwitchToDistrict: (startDistrict: string, endDistrict: string) => void;
}) {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const exactParams = { start_point: fromPointId, end_point: toPointId, date };
  const districtParams =
    fromDistrict && toDistrict
      ? { start_district: fromDistrict, end_district: toDistrict, date }
      : null;

  const exactQ = useQuery({
    queryKey: queryKeys.searchTrips(exactParams),
    queryFn: () => api.searchTrips(exactParams),
    enabled: mode === "exact",
  });

  const districtQ = useQuery({
    queryKey: queryKeys.searchTrips(districtParams ?? {}),
    queryFn: () => api.searchTrips(districtParams!),
    enabled: mode === "district" && districtParams != null,
  });

  const tripsQ = mode === "exact" ? exactQ : districtQ;
  const fallback = exactQ.data?.districtFallback;
  const allTrips = useMemo(
    () => sortTripsByTime(tripsQ.data?.trips ?? []),
    [tripsQ.data?.trips],
  );

  const [filters, setFilters] = useState<SearchTripFilters>(EMPTY_SEARCH_FILTERS);
  const [filterOpen, setFilterOpen] = useState(false);

  const filteredTrips = useMemo(() => applyTripFilters(allTrips, filters), [allTrips, filters]);
  const trips = filteredTrips.map(apiTripToCard);
  const filtersActive = searchFiltersActive(filters);

  const routeLabel =
    mode === "district" && fromDistrict && toDistrict
      ? `${fromDistrict} → ${toDistrict}`
      : `${fromLabel} → ${toLabel}`;

  if (tripsQ.isLoading || (mode === "exact" && exactQ.isLoading)) {
    return (
      <>
        <ScreenHeader title="Поиск…" />
        <Section>
          <div className="h-40 bg-secondary animate-pulse rounded-xl" />
        </Section>
      </>
    );
  }

  if (mode === "exact" && allTrips.length === 0) {
    const sd = fallback?.startDistrict ?? fromDistrict;
    const ed = fallback?.endDistrict ?? toDistrict;
    return (
      <>
        <ScreenHeader title="Доступные поездки" subtitle={formatTripDate(date)} />
        <EmptyState
          icon={<SearchIcon className="size-6" />}
          title="На эту дату точных поездок нет"
          description={
            sd && ed
              ? `Можно расширить поиск: все поездки между районами «${sd}» и «${ed}».`
              : "Попробуйте другую дату или маршрут."
          }
          action={
            <div className="flex flex-col gap-2 w-full max-w-xs">
              {sd && ed ? (
                <button
                  type="button"
                  onClick={() => onSwitchToDistrict(sd, ed)}
                  className="h-12 rounded-xl brand-gradient font-bold press inline-flex items-center justify-center gap-2"
                >
                  <MapPin className="size-4" />
                  Искать: {sd} → {ed}
                </button>
              ) : null}
              <button
                type="button"
                onClick={onChangeDate}
                className="h-12 rounded-xl bg-secondary text-secondary-foreground font-semibold press inline-flex items-center justify-center gap-2"
              >
                <CalendarDays className="size-4" />
                Выбрать другую дату
              </button>
            </div>
          }
        />
      </>
    );
  }

  if (mode === "district" && allTrips.length === 0) {
    return (
      <>
        <ScreenHeader title="Доступные поездки" subtitle={`${routeLabel} · ${formatTripDate(date)}`} />
        <EmptyState
          icon={<SearchIcon className="size-6" />}
          title="Поездок на эту дату нет"
          description="Попробуйте выбрать другую дату для этого маршрута."
          action={
            <button
              type="button"
              onClick={onChangeDate}
              className="h-12 px-6 rounded-xl bg-secondary text-secondary-foreground font-semibold press inline-flex items-center justify-center gap-2"
            >
              <CalendarDays className="size-4" />
              Выбрать другую дату
            </button>
          }
        />
      </>
    );
  }

  if (allTrips.length > 0 && filteredTrips.length === 0) {
    return (
      <>
        <ScreenHeader
          title="Доступные поездки"
          subtitle={`${routeLabel} · ${formatTripDate(date)}`}
          right={<FilterButton active={filtersActive} onClick={() => setFilterOpen(true)} />}
        />
        <EmptyState
          icon={<SearchIcon className="size-6" />}
          title="Нет поездок по фильтру"
          description="Измените время или число свободных мест."
          action={
            <button
              type="button"
              onClick={() => setFilters(EMPTY_SEARCH_FILTERS)}
              className="h-12 px-6 rounded-xl bg-secondary text-secondary-foreground font-semibold press"
            >
              Сбросить фильтр
            </button>
          }
        />
        {filterOpen ? (
          <SearchFilterSheet
            filters={filters}
            onApply={setFilters}
            onClose={() => setFilterOpen(false)}
          />
        ) : null}
      </>
    );
  }

  return (
    <>
      <ScreenHeader
        title="Доступные поездки"
        subtitle={
          mode === "district"
            ? `${routeLabel} · ${formatTripDate(date)} · ${trips.length} из ${allTrips.length}`
            : `${formatTripDate(date)} · ${trips.length}${filtersActive ? ` из ${allTrips.length}` : ""}`
        }
        right={<FilterButton active={filtersActive} onClick={() => setFilterOpen(true)} />}
      />
      {mode === "district" && fromDistrict && toDistrict ? (
        <Section>
          <p className="text-xs text-muted-foreground px-1">
            Показаны все поездки между районами. Точные остановки могут отличаться — маршрут сохранён для
            быстрого поиска.
          </p>
        </Section>
      ) : null}
      <Section>
        <div className="space-y-3">
          {trips.map((t) => (
            <div key={t.id} className="rounded-xl">
              <TripCard
                trip={t}
                onClick={() => {
                  haptic("light");
                  navigate({ to: "/trip/$id", params: { id: t.id } });
                }}
              />
            </div>
          ))}
        </div>
      </Section>
      {filterOpen ? (
        <SearchFilterSheet filters={filters} onApply={setFilters} onClose={() => setFilterOpen(false)} />
      ) : null}
    </>
  );
}
