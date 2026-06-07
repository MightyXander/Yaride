import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomNav } from "../../components/BottomNav";
import { LoadingView, ErrorView } from "../../components/States";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useFlow, type FlowMode } from "../../state/FlowContext";
import { haptic } from "../../telegram/webapp";

type Leg = "start" | "end";

// Иконки/цвета плашек районов (детерминированно по имени, чтобы совпадало с макетом).
const DISTRICT_STYLE: Record<string, { icon: string; bg: string }> = {
  Дзержинский: { icon: "apartment", bg: "bg-primary-fixed text-on-primary-fixed-variant" },
  Заволжский: { icon: "pool", bg: "bg-secondary-fixed text-on-secondary-fixed-variant" },
  Кировский: { icon: "account_balance", bg: "bg-tertiary-fixed text-on-tertiary-fixed-variant" },
  Красноперекопский: { icon: "factory", bg: "bg-primary-fixed text-on-primary-fixed-variant" },
  Ленинский: { icon: "architecture", bg: "bg-surface-container-high text-on-surface-variant" },
  Фрунзенский: { icon: "directions_bus", bg: "bg-secondary-fixed text-on-secondary-fixed-variant" },
};

function styleFor(name: string) {
  for (const key of Object.keys(DISTRICT_STYLE)) {
    if (name.startsWith(key)) return DISTRICT_STYLE[key];
  }
  return { icon: "location_city", bg: "bg-surface-container-high text-on-surface-variant" };
}

function titleFor(mode: FlowMode, leg: Leg): string {
  if (mode === "create") {
    return leg === "start" ? "Старт поездки: выбери район посадки" : "Финиш поездки: выбери район высадки";
  }
  return leg === "start" ? "Откуда едем: выбери район посадки" : "Куда едем: выбери район высадки";
}

export function SelectDistrict() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const mode = (params.get("mode") as FlowMode) ?? "search";
  const leg = (params.get("leg") as Leg) ?? "start";
  const { reset } = useFlow();
  const [geoBusy, setGeoBusy] = useState(false);

  // Старт нового маршрута — сбрасываем flow и фиксируем режим.
  useEffect(() => {
    if (leg === "start") reset(mode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(() => api.districts(), []);
  const { data, loading, error, reload } = useApi(load, []);

  const pick = (name: string) => {
    haptic("light");
    navigate(`/route/stop?mode=${mode}&leg=${leg}&district=${encodeURIComponent(name)}`);
  };

  const useGeo = () => {
    if (!navigator.geolocation || geoBusy) return;
    setGeoBusy(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const res = await api.nearestStops(pos.coords.latitude, pos.coords.longitude);
          const nearest = res.stops[0];
          if (nearest?.district) {
            pick(nearest.district);
            return;
          }
        } catch {
          /* падаем в ручной выбор */
        } finally {
          setGeoBusy(false);
        }
      },
      () => setGeoBusy(false),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  };

  if (loading) return <LoadingView />;
  if (error) return <ErrorView message={error} onRetry={reload} />;

  const districts = data?.districts ?? [];

  return (
    <>
      <Header title="Yaride" onBack={() => navigate(-1)} />
      <div className="fixed top-14 left-0 h-0.5 w-full bg-surface-container-highest z-[60]">
        <div className="h-full bg-primary" style={{ width: leg === "start" ? "20%" : "55%" }} />
      </div>

      <main className="pt-24 pb-24 px-margin-page min-h-screen">
        <nav className="flex items-center gap-1 mb-4 text-on-surface-variant">
          <span className="font-label-md text-label-md">Ярославль</span>
          <Icon name="chevron_right" className="text-[14px]" />
          <span className="font-label-md text-label-md text-primary font-bold">Район</span>
        </nav>

        <section className="mb-6">
          <h2 className="font-headline-lg text-headline-lg-mobile text-on-surface mb-2">{titleFor(mode, leg)}</h2>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Выберите район города для более точного поиска попутчиков
          </p>
        </section>

        {leg === "start" && (
          <button
            onClick={useGeo}
            disabled={geoBusy}
            className="w-full mb-8 flex items-center justify-center gap-2 py-4 px-6 bg-primary text-on-primary rounded-xl font-headline-md text-[17px] active:scale-[0.97] transition-all disabled:opacity-60"
          >
            <Icon name={geoBusy ? "progress_activity" : "my_location"} filled className={geoBusy ? "animate-spin" : ""} />
            {geoBusy ? "Определяем…" : "Отправить геолокацию"}
          </button>
        )}

        <div className="grid grid-cols-1 gap-gutter-stack">
          {districts.map((name) => {
            const s = styleFor(name);
            return (
              <button
                key={name}
                onClick={() => pick(name)}
                className="flex items-center justify-between p-padding-card bg-surface-container-lowest rounded-xl border border-outline-variant/20 transition-all active:scale-[0.98] group text-left"
              >
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${s.bg}`}>
                    <Icon name={s.icon} />
                  </div>
                  <span className="font-body-lg text-body-lg text-on-surface font-medium">{name}</span>
                </div>
                <Icon name="chevron_right" className="text-outline-variant group-hover:text-primary" />
              </button>
            );
          })}
        </div>
      </main>

      <BottomNav />
    </>
  );
}
