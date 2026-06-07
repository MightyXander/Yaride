import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { BottomNav } from "../../components/BottomNav";
import { TripCard } from "../../components/TripCard";
import { BottomActionButton } from "../../components/BottomActionButton";
import { LoadingView, ErrorView, EmptyView } from "../../components/States";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useFlow } from "../../state/FlowContext";
import { haptic } from "../../telegram/webapp";

// Результаты поиска поездок по маршруту из flow (точки посадки/высадки).
export function SearchResults() {
  const navigate = useNavigate();
  const { flow } = useFlow();
  const [selected, setSelected] = useState<number | null>(null);

  const load = useCallback(
    () =>
      api.searchTrips({
        start_point: flow.startPointId ?? undefined,
        end_point: flow.endPointId ?? undefined,
      }),
    [flow.startPointId, flow.endPointId],
  );
  const { data, loading, error, reload } = useApi(load, [flow.startPointId, flow.endPointId]);

  const select = (id: number) => {
    haptic("light");
    setSelected((prev) => (prev === id ? null : id));
  };

  if (loading) return <LoadingView />;
  if (error) return <ErrorView message={error} onRetry={reload} />;

  const trips = data?.trips ?? [];

  return (
    <>
      <Header title="Доступные поездки" rightIcon="tune" onBack={() => navigate(-1)} />

      <main className="pt-20 pb-32 px-margin-page min-h-screen flex flex-col gap-gutter-stack">
        <div className="flex justify-between items-center mb-2">
          <span className="text-label-md font-label-md text-on-surface-variant uppercase tracking-wider">
            Найдено: {trips.length}
          </span>
          <span className="text-label-md font-label-md text-primary">Ярославль</span>
        </div>

        {trips.length === 0 ? (
          <EmptyView
            icon="search_off"
            title="Подходящих поездок пока нет"
            subtitle="Попробуйте изменить время или маршрут поиска"
          />
        ) : (
          trips.map((t) => (
            <TripCard key={t.id} trip={t} selected={selected === t.id} onClick={() => select(t.id)} />
          ))
        )}
      </main>

      {selected != null ? (
        <BottomActionButton label="Подробнее о поездке" onClick={() => navigate(`/ride/${selected}`)} withArrow />
      ) : (
        <BottomNav />
      )}
    </>
  );
}
