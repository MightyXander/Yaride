import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { Avatar } from "../../components/TripCard";
import { RouteTimeline } from "../../components/RouteTimeline";
import { SeatsIndicator } from "../../components/SeatsIndicator";
import { BottomActionButton } from "../../components/BottomActionButton";
import { LoadingView, ErrorView } from "../../components/States";
import { api, ApiError } from "../../api/client";
import { useApi } from "../../api/useApi";
import { haptic } from "../../telegram/webapp";

// Детали поездки: маршрут, водитель+авто, цена, места, комментарий → бронирование.
export function RideDetails() {
  const navigate = useNavigate();
  const { id } = useParams();
  const tripId = Number(id);
  const [booking, setBooking] = useState(false);
  const [bookError, setBookError] = useState<string | null>(null);

  const load = useCallback(() => api.trip(tripId), [tripId]);
  const { data: trip, loading, error, reload } = useApi(load, [tripId]);

  const book = async () => {
    if (booking) return;
    haptic("medium");
    setBooking(true);
    setBookError(null);
    try {
      await api.book(tripId);
      navigate("/booking/confirm", { state: { tripId } });
    } catch (e) {
      setBookError(e instanceof ApiError ? e.message : "Не удалось забронировать");
      setBooking(false);
    }
  };

  if (loading) return <LoadingView />;
  if (error || !trip) return <ErrorView message={error ?? "Поездка не найдена"} onRetry={reload} />;

  return (
    <>
      <Header title="Поездка" centerTitle rightIcon="share" onBack={() => navigate(-1)} />

      <main className="pt-20 pb-32 px-margin-page flex flex-col gap-4">
        <p className="font-body-md text-body-md text-on-surface-variant">{trip.whenLabel}</p>

        <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20">
          <RouteTimeline from={trip.fromTitle} to={trip.toTitle} labels />
        </div>

        <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar name={trip.driverName ?? "Водитель"} size={48} />
            <div>
              <p className="font-headline-md text-headline-md-mobile text-on-surface">{trip.driverName}</p>
              <div className="flex items-center gap-1 text-label-md font-label-md text-on-surface-variant">
                <Icon name="star" filled className="text-tertiary text-[16px]" />
                {trip.driverRating.toFixed(1)}
                {trip.driverTripsCount != null && <span> · {trip.driverTripsCount} поездок</span>}
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20">
            <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider mb-1">Автомобиль</p>
            {trip.carModel ? (
              <>
                <p className="font-body-lg text-body-lg font-bold text-on-surface">{trip.carModel}</p>
                <p className="font-label-md text-label-md text-on-surface-variant">
                  {[trip.carColor, trip.carPlate].filter(Boolean).join(" • ")}
                </p>
              </>
            ) : (
              <p className="font-body-md text-body-md text-on-surface-variant">Не указан</p>
            )}
          </div>
          <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20">
            <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider mb-1">Стоимость</p>
            <p className="font-headline-md text-headline-md text-primary tabular-nums">{trip.priceRub} руб.</p>
            <p className="font-label-md text-label-md text-on-surface-variant">за 1 место</p>
          </div>
        </div>

        <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20">
          <div className="flex items-center justify-between mb-3">
            <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Свободные места</p>
            <span className="bg-secondary/10 text-secondary px-3 py-1 rounded-full text-label-sm font-label-sm">
              {trip.seatsFree} доступно
            </span>
          </div>
          <SeatsIndicator total={trip.seatsTotal} free={trip.seatsFree} />
        </div>

        {trip.comment && (
          <div className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20">
            <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider mb-2">Комментарий водителя</p>
            <p className="font-body-md text-body-md text-on-surface italic">«{trip.comment}»</p>
          </div>
        )}

        {bookError && <p className="text-center text-label-md font-label-md text-error">{bookError}</p>}
      </main>

      <BottomActionButton
        label={booking ? "Бронируем…" : "Забронировать"}
        onClick={book}
        disabled={booking || trip.seatsFree <= 0}
        loading={booking}
        withArrow={!booking}
      />
    </>
  );
}
