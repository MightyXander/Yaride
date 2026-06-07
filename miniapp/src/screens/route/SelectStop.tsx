import { useCallback, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { LoadingView, ErrorView, EmptyView } from "../../components/States";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useFlow, type FlowMode } from "../../state/FlowContext";
import { haptic } from "../../telegram/webapp";

type Leg = "start" | "end";

// Выбор остановки внутри района (с поиском по названию). Сохраняет точку во flow.
export function SelectStop() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const mode = (params.get("mode") as FlowMode) ?? "search";
  const leg = (params.get("leg") as Leg) ?? "start";
  const district = params.get("district") ?? "";
  const { patch } = useFlow();
  const [query, setQuery] = useState("");

  const load = useCallback(() => api.stops(district), [district]);
  const { data, loading, error, reload } = useApi(load, [district]);

  const filtered = useMemo(
    () => (data?.stops ?? []).filter((s) => s.title.toLowerCase().includes(query.toLowerCase())),
    [data, query],
  );

  const pick = (stop: { id: number; title: string }) => {
    haptic("light");
    const label = `${district} (${stop.title})`;
    if (leg === "start") {
      patch({ startPointId: stop.id, startLabel: label });
      navigate(`/route/district?mode=${mode}&leg=end`);
    } else {
      patch({ endPointId: stop.id, endLabel: label });
      navigate(mode === "search" ? "/search/results" : "/create/date-time");
    }
  };

  if (loading) return <LoadingView />;
  if (error) return <ErrorView message={error} onRetry={reload} />;

  return (
    <>
      <Header title={`Ярославль › ${district}`} centerTitle onBack={() => navigate(-1)} />

      <main className="pt-20 pb-24 px-margin-page min-h-screen flex flex-col">
        <div className="mt-2 mb-6">
          <p className="font-label-sm text-label-sm text-on-surface-variant mb-1 uppercase tracking-wider">
            {district} район
          </p>
          <h2 className="font-headline-lg text-headline-lg-mobile font-bold text-on-surface">
            {leg === "start" ? "Остановка посадки" : "Остановка высадки"}
          </h2>
        </div>

        <div className="bg-surface-container rounded-lg px-4 py-3 flex items-center gap-3 mb-6">
          <Icon name="search" className="text-outline" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск остановки"
            className="bg-transparent border-none p-0 focus:outline-none w-full font-body-lg text-body-lg text-on-surface placeholder:text-outline/50"
          />
        </div>

        {filtered.length === 0 ? (
          <EmptyView icon="wrong_location" title="Остановки не найдены" />
        ) : (
          <div className="space-y-2 flex-grow">
            {filtered.map((s) => (
              <button
                key={s.id}
                onClick={() => pick(s)}
                className="w-full bg-surface-container-low p-4 rounded-xl flex items-center justify-between transition-colors active:scale-[0.98] text-left"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Icon name="location_on" className="text-outline shrink-0" />
                  <div className="min-w-0">
                    <p className="font-body-lg text-body-lg text-on-surface truncate">{s.title}</p>
                    <p className="font-label-sm text-label-sm text-on-surface-variant truncate">{s.adminArea}</p>
                  </div>
                </div>
                <Icon name="chevron_right" className="text-outline-variant shrink-0" />
              </button>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
