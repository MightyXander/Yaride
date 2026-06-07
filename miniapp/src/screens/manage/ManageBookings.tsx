import { useCallback, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { Avatar } from "../../components/TripCard";
import { LoadingView, ErrorView, EmptyView } from "../../components/States";
import { api, ApiError, type ApiTrip } from "../../api/client";
import { useApi } from "../../api/useApi";

// Детали поездки водителя: маршрут/цена, активные брони (отклонить), отмена поездки целиком.
export function ManageBookings() {
  const navigate = useNavigate();
  const location = useLocation();
  const trip = (location.state as { trip?: ApiTrip } | null)?.trip ?? null;
  const tripId = trip?.id ?? 0;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api.manageTripBookings(tripId), [tripId]);
  const { data, loading, error: loadError, reload } = useApi(load, [tripId]);

  const reject = async (bookingId: number) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.rejectBooking(bookingId);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось отклонить бронь");
    } finally {
      setBusy(false);
    }
  };

  const cancelTrip = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelTrip(tripId);
      navigate("/manage");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось отменить поездку");
      setBusy(false);
    }
  };

  if (!trip) return <ErrorView message="Поездка не выбрана" onRetry={() => navigate("/manage")} />;
  if (loading) return <LoadingView />;
  if (loadError) return <ErrorView message={loadError} onRetry={reload} />;

  const bookings = (data?.bookings ?? []).filter((b) => b.status === "active");

  return (
    <>
      <Header title="Детали поездки" centerTitle onBack={() => navigate(-1)} />

      <main className="pt-20 pb-24 px-margin-page flex flex-col gap-4">
        <div className="bg-surface-container-low rounded-xl p-padding-card border border-outline-variant/20">
          <div className="flex justify-between items-start">
            <div>
              <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Маршрут</p>
              <p className="font-headline-md text-headline-md-mobile text-on-surface mt-1">
                {trip.fromTitle} <Icon name="arrow_forward" className="text-[16px] text-outline align-middle" /> {trip.toTitle}
              </p>
            </div>
            <div className="text-right">
              <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Цена</p>
              <p className="font-headline-md text-headline-md-mobile text-primary tabular-nums mt-1">{trip.priceRub} ₽</p>
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-outline-variant/10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Icon name="schedule" className="text-primary" />
              </div>
              <div>
                <p className="font-label-sm text-label-sm text-outline">Время отправления</p>
                <p className="font-body-md text-body-md font-bold text-on-surface">{trip.whenLabel}</p>
              </div>
            </div>
            <span className="bg-secondary/10 text-secondary px-3 py-1.5 rounded-full text-label-md font-label-md flex items-center gap-1">
              <Icon name="event_seat" className="text-[16px]" />
              {trip.seatsFree} мест
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between mt-2">
          <h3 className="font-headline-md text-headline-md-mobile text-on-surface">Пассажиры</h3>
          <span className="bg-surface-container-high text-on-surface-variant px-3 py-1 rounded-full text-label-sm font-label-sm">
            {bookings.length} забронировано
          </span>
        </div>

        {bookings.length === 0 ? (
          <EmptyView icon="group" title="Пока нет броней" />
        ) : (
          bookings.map((p) => (
            <div
              key={p.bookingId}
              className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20 flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="relative shrink-0">
                  <Avatar name={p.passengerName ?? "?"} size={48} />
                  {p.passengerRating != null && (
                    <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-surface-container-lowest px-1 rounded-full text-label-sm font-label-sm text-tertiary flex items-center">
                      <Icon name="star" filled className="text-[12px]" />
                      {p.passengerRating.toFixed(1)}
                    </span>
                  )}
                </div>
                <p className="font-body-lg text-body-lg text-on-surface truncate">{p.passengerName}</p>
              </div>
              <button
                onClick={() => reject(p.bookingId)}
                disabled={busy}
                className="shrink-0 px-4 h-10 rounded-lg border border-error/40 text-error font-label-md text-label-md active:scale-95 transition-transform disabled:opacity-50"
              >
                Отклонить
              </button>
            </div>
          ))
        )}

        <div className="flex gap-3 p-padding-card bg-error-container/30 border border-error/10 rounded-xl items-start mt-2">
          <Icon name="warning" filled className="text-error shrink-0" />
          <p className="font-body-md text-body-md text-on-error-container leading-snug">
            При отмене поездки все брони будут аннулированы, а пассажиры получат уведомление.
          </p>
        </div>

        {error && <p className="text-center text-label-md font-label-md text-error">{error}</p>}

        <button
          onClick={cancelTrip}
          disabled={busy}
          className="w-full h-14 rounded-xl bg-error text-on-error font-headline-md-mobile font-bold flex items-center justify-center gap-2 active:scale-95 transition-transform shadow-lg shadow-error/20 disabled:opacity-50"
        >
          <Icon name={busy ? "progress_activity" : "cancel"} className={busy ? "animate-spin" : ""} />
          Отменить поездку полностью
        </button>
      </main>
    </>
  );
}
