import { useCallback, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { Avatar } from "../../components/TripCard";
import { LoadingView } from "../../components/States";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";

// Подтверждение брони: успех + сводка поездки + добавление маршрута в избранное.
export function BookingConfirmation() {
  const navigate = useNavigate();
  const location = useLocation();
  const tripId = (location.state as { tripId?: number } | null)?.tripId ?? null;
  const [fav, setFav] = useState(false);
  const [favBusy, setFavBusy] = useState(false);

  const load = useCallback(() => (tripId ? api.trip(tripId) : Promise.resolve(null)), [tripId]);
  const { data: trip, loading } = useApi(load, [tripId]);

  const addFav = async () => {
    if (!tripId || favBusy || fav) return;
    setFavBusy(true);
    try {
      await api.addFavorite({ trip_id: tripId });
      setFav(true);
    } catch {
      /* игнорируем — не критично */
    } finally {
      setFavBusy(false);
    }
  };

  if (loading) return <LoadingView />;

  return (
    <>
      <Header title="Yaride" centerTitle onBack={() => navigate("/")} />

      <main className="pt-20 pb-32 px-margin-page">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-20 h-20 bg-secondary-container rounded-full flex items-center justify-center mb-6">
            <Icon name="check_circle" filled className="text-on-secondary-container !text-5xl" />
          </div>
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface mb-2">Поездка забронирована!</h2>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-[280px]">
            {trip ? `Водитель ${trip.driverName ?? ""} получил вашу бронь.` : "Бронь создана."}
          </p>
        </div>

        {trip && (
          <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20 mb-gutter-stack space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Avatar name={trip.driverName ?? "Водитель"} size={48} />
                <div>
                  <p className="font-label-md text-label-md text-on-surface">
                    {trip.driverName} • ★ {trip.driverRating.toFixed(1)}
                  </p>
                  {trip.carModel && (
                    <p className="font-label-sm text-label-sm text-on-surface-variant">
                      {[trip.carModel, trip.carPlate].filter(Boolean).join(" • ")}
                    </p>
                  )}
                </div>
              </div>
              <p className="font-headline-md text-headline-md-mobile text-secondary font-bold">{trip.priceRub} ₽</p>
            </div>
            <div className="flex items-center gap-2 pt-3 border-t border-outline-variant/10">
              <Icon name="calendar_month" className="text-on-surface-variant !text-[18px]" />
              <p className="font-label-md text-label-md text-on-surface">{trip.whenLabel}</p>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <button
            onClick={addFav}
            disabled={favBusy}
            className={`w-full h-12 flex items-center justify-center gap-2 font-label-md text-label-md rounded-xl active:scale-[0.98] transition-all ${
              fav ? "bg-tertiary-fixed text-on-tertiary-fixed-variant" : "bg-surface-container-high text-primary"
            }`}
          >
            <Icon name="favorite" filled={fav} />
            {fav ? "Маршрут в избранном" : "Добавить маршрут в избранное"}
          </button>
          <button
            onClick={() => navigate("/bookings")}
            className="w-full h-12 flex items-center justify-center gap-2 bg-transparent text-on-surface-variant font-label-md text-label-md rounded-xl active:opacity-70"
          >
            <Icon name="list_alt" />
            Перейти в мои брони
          </button>
        </div>

        <button
          onClick={() => navigate("/")}
          className="w-full h-14 mt-6 bg-primary text-on-primary font-headline-md rounded-xl active:scale-95 transition-transform"
        >
          На главную
        </button>
      </main>
    </>
  );
}
