import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomNav } from "../../components/BottomNav";
import { StatusBadge, type BookingStatus } from "../../components/StatusBadge";
import { LoadingView, ErrorView, EmptyView } from "../../components/States";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";

const STATE_MAP: Record<string, { status: BookingStatus; label: string }> = {
  active: { status: "active", label: "Активна" },
  cancelled_by_passenger: { status: "cancelled", label: "Отменена вами" },
  cancelled_by_driver: { status: "cancelled", label: "Отменил водитель" },
};

// Список броней пассажира со статусами; активную можно отменить.
export function MyBookings() {
  const navigate = useNavigate();
  const load = useCallback(() => api.myBookings(), []);
  const { data, loading, error, reload } = useApi(load, []);

  if (loading) return <LoadingView />;
  if (error) return <ErrorView message={error} onRetry={reload} />;

  const bookings = data?.bookings ?? [];

  return (
    <>
      <Header title="Мои брони" onBack={() => navigate("/")} />

      <main className="pt-20 pb-24 px-margin-page min-h-screen flex flex-col gap-gutter-stack">
        {bookings.length === 0 ? (
          <EmptyView
            icon="confirmation_number"
            title="У тебя пока нет броней"
            subtitle="Найди поездку и забронируй место — она появится здесь"
          />
        ) : (
          bookings.map((b) => {
            const meta = STATE_MAP[b.status] ?? { status: "draft" as BookingStatus, label: b.status };
            return (
              <div key={b.id} className="bg-surface-container-low rounded-xl p-padding-card border border-outline-variant/20">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Бронь #{b.id}</p>
                    <p className="font-headline-md text-headline-md-mobile text-on-surface mt-1">
                      {b.fromTitle} → {b.toTitle}
                    </p>
                  </div>
                  <StatusBadge status={meta.status} label={meta.label} />
                </div>

                <div className="flex items-center justify-between text-on-surface-variant">
                  <span className="flex items-center gap-2 font-body-md text-body-md">
                    <Icon name="schedule" className="text-[18px]" />
                    {b.whenLabel}
                  </span>
                  <span className="font-body-md text-body-md text-primary tabular-nums">{b.priceRub} ₽</span>
                </div>

                {b.status === "cancelled_by_driver" && b.cancelReason && (
                  <p className="mt-3 pt-3 border-t border-outline-variant/10 font-label-md text-label-md text-on-surface-variant">
                    Причина: {b.cancelReason}
                  </p>
                )}

                {b.status === "active" && (
                  <button
                    onClick={() =>
                      navigate("/booking/cancel", {
                        state: { bookingId: b.id, fromTitle: b.fromTitle, toTitle: b.toTitle, whenLabel: b.whenLabel },
                      })
                    }
                    className="mt-4 w-full h-11 rounded-lg border border-error/30 text-error font-label-md text-label-md flex items-center justify-center gap-2 active:scale-[0.98] transition-transform"
                  >
                    <Icon name="cancel" className="text-[18px]" />
                    Отменить бронь
                  </button>
                )}
              </div>
            );
          })
        )}
      </main>

      <BottomNav />
    </>
  );
}
