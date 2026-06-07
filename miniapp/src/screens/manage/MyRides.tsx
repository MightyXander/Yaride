import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomNav } from "../../components/BottomNav";
import { LoadingView, ErrorView, EmptyView } from "../../components/States";
import { api, type ApiTrip } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useUser } from "../../state/UserContext";

// Экран водителя «Управление»: список своих поездок + переход к настройке порога рейтинга и статистике.
export function MyRides() {
  const navigate = useNavigate();
  const { me } = useUser();
  const load = useCallback(() => api.manageTrips(), []);
  const { data, loading, error, reload } = useApi(load, []);

  if (loading) return <LoadingView />;
  if (error) return <ErrorView message={error} onRetry={reload} />;

  const trips = (data?.trips ?? []).filter((t) => t.status === "open");
  const rating = me?.user?.ratingAvg ?? 0;
  const tripsCount = me?.user?.tripsDriverCount ?? trips.length;

  return (
    <>
      <Header title="Управление" onBack={() => navigate("/")} />

      <main className="pt-20 pb-24 px-margin-page min-h-screen flex flex-col gap-6">
        <section>
          <h3 className="font-label-md text-label-md text-outline mb-3 uppercase tracking-widest">Настройки безопасности</h3>
          <button
            onClick={() => navigate("/manage/threshold")}
            className="w-full flex items-center gap-4 bg-surface-container-low p-padding-card rounded-xl border border-outline-variant/20 text-left active:scale-[0.98] transition-transform"
          >
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Icon name="shield" className="text-primary" />
            </div>
            <div className="flex-1">
              <p className="font-body-md text-body-md text-on-surface">Порог рейтинга пассажиров</p>
              <p className="font-label-md text-label-md text-secondary">Настроить минимальный рейтинг</p>
            </div>
            <Icon name="chevron_right" className="text-outline-variant" />
          </button>
        </section>

        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-label-md text-label-md text-outline uppercase tracking-widest">Ваши поездки</h3>
            <span className="bg-primary/10 text-primary px-3 py-1 rounded-full text-label-sm font-label-sm">
              Активные: {trips.length}
            </span>
          </div>

          {trips.length === 0 ? (
            <EmptyView icon="directions_car" title="Нет активных поездок" subtitle="Создай поездку кнопкой ниже" />
          ) : (
            <div className="flex flex-col gap-gutter-stack">
              {trips.map((t) => (
                <TripRow key={t.id} trip={t} onClick={() => navigate("/manage/bookings", { state: { trip: t } })} />
              ))}
            </div>
          )}
        </section>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-primary text-on-primary p-padding-card rounded-xl">
            <Icon name="directions_car" className="mb-2" />
            <p className="font-label-md text-label-md opacity-90">Поездок водителем</p>
            <p className="font-headline-md text-headline-md tabular-nums">{tripsCount}</p>
          </div>
          <div className="bg-surface-container p-padding-card rounded-xl">
            <Icon name="star" filled className="text-tertiary mb-2" />
            <p className="font-label-md text-label-md text-on-surface-variant">Ваш рейтинг</p>
            <p className="font-headline-md text-headline-md text-on-surface tabular-nums">{rating.toFixed(2)}</p>
          </div>
        </div>
      </main>

      <button
        onClick={() => navigate("/create")}
        className="fixed bottom-20 right-4 z-40 w-14 h-14 rounded-full bg-primary text-on-primary shadow-lg shadow-primary/30 flex items-center justify-center active:scale-95 transition-transform"
      >
        <Icon name="add" size={28} />
      </button>

      <BottomNav />
    </>
  );
}

function TripRow({ trip, onClick }: { trip: ApiTrip; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20 text-left active:scale-[0.98] transition-transform"
    >
      <div className="flex justify-between items-start">
        <div className="min-w-0">
          <p className="font-label-md text-label-md text-on-surface-variant">{trip.whenLabel}</p>
          <p className="font-body-lg text-body-lg text-on-surface mt-0.5">
            {trip.fromTitle} <Icon name="arrow_forward" className="text-[14px] text-outline align-middle" /> {trip.toTitle}
          </p>
        </div>
        <span className="shrink-0 bg-secondary/10 text-secondary px-3 py-1.5 rounded-lg text-label-sm font-label-sm">
          {trip.priceRub} ₽
        </span>
      </div>
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-outline-variant/10">
        {trip.seatsFree === 0 ? (
          <span className="font-label-md text-label-md text-secondary font-semibold flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-secondary" /> Мест нет
          </span>
        ) : (
          <span className="font-label-md text-label-md text-on-surface-variant">Свободных мест: {trip.seatsFree}</span>
        )}
        <Icon name="chevron_right" className="text-outline-variant" />
      </div>
    </button>
  );
}
