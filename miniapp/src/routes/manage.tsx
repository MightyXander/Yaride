import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Filter, Star, Users } from "lucide-react";
import { YandexRouteCard } from "@/components/yandex-route-card";
import {
  BottomCTA,
  Card,
  Chip,
  EmptyState,
  Screen,
  ScreenHeader,
  Section,
  StatusBadge,
  TripCard,
} from "@/components/ui-kit";
import { api } from "@/lib/api";
import { apiTripToCard } from "@/lib/adapters";
import { isActiveDriver } from "@/lib/driver-access";
import { manageBookingsQueryOptions, manageTripsQueryOptions, meQueryOptions, queryKeys } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";
import { tripHasRouteCoords } from "@/lib/yandex-navigator";

export const Route = createFileRoute("/manage")({
  component: ManageScreen,
});

const THRESHOLDS = ["off", "3.0", "4.0", "4.5"] as const;
type Threshold = (typeof THRESHOLDS)[number];

function thresholdFromUser(rating?: number | null): Threshold {
  if (rating == null || rating <= 0) return "off";
  const label = rating.toFixed(1);
  return THRESHOLDS.includes(label as Threshold) ? (label as Threshold) : "off";
}

function ManageScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const meQ = useQuery(meQueryOptions());
  const tripsQ = useQuery({ ...manageTripsQueryOptions(), enabled: isActiveDriver(meQ.data?.user) });
  const [confirmCancel, setConfirmCancel] = useState<number | null>(null);
  const [bookingsTripId, setBookingsTripId] = useState<number | null>(null);

  const thresholdMut = useMutation({
    mutationFn: (t: Threshold) => api.setPassengerRatingThreshold(t === "off" ? "off" : t),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.me }),
  });

  const cancelTripMut = useMutation({
    mutationFn: (tripId: number) => api.cancelTrip(tripId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.manageTrips });
      haptic("warning");
      setConfirmCancel(null);
      setBookingsTripId(null);
    },
  });

  const user = meQ.data?.user;
  const threshold = thresholdFromUser(user?.minPassengerRating);
  const bookingsTrip = (tripsQ.data?.trips ?? []).find((t) => t.id === bookingsTripId) ?? null;
  const bookingsQ = useQuery({
    ...manageBookingsQueryOptions(bookingsTripId ?? 0),
    enabled: bookingsTripId != null,
  });

  const rejectMut = useMutation({
    mutationFn: (bookingId: number) => api.rejectBooking(bookingId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.manageBookings(bookingsTripId!) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.manageTrips });
      haptic("warning");
    },
  });

  useBackButton(() => {
    if (confirmCancel) setConfirmCancel(null);
    else if (bookingsTripId) setBookingsTripId(null);
    else navigate({ to: "/home" });
  });

  if (!isActiveDriver(user)) {
    return (
      <Screen>
        <ScreenHeader title="Только для водителей" subtitle="Дождитесь одобления заявки" />
      </Screen>
    );
  }

  if (confirmCancel) {
    return (
      <Screen>
        <ScreenHeader title="Отменить поездку?" subtitle="Все активные брони будут аннулированы" />
        <BottomCTA
          text="Да, отменить"
          variant="destructive"
          onClick={() => cancelTripMut.mutate(confirmCancel)}
        />
      </Screen>
    );
  }

  if (bookingsTripId && bookingsTrip) {
    const bookings = bookingsQ.data?.bookings ?? [];
    return (
      <Screen>
        <ScreenHeader
          title="Брони пассажиров"
          subtitle={`${bookingsTrip.fromTitle} → ${bookingsTrip.toTitle}`}
        />
        <Section>
          {bookingsQ.isLoading ? (
            <div className="h-32 bg-secondary animate-pulse rounded-xl" />
          ) : bookings.length === 0 ? (
            <EmptyState title="Броней пока нет" description="Активные брони появятся здесь." />
          ) : (
            <div className="space-y-3">
              {bookings.map((b) => (
                <Card key={b.bookingId} className="!p-4">
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <div className="font-semibold">{b.passengerName ?? "Пассажир"}</div>
                    <StatusBadge
                      status={
                        b.status as "active" | "cancelled_by_passenger" | "cancelled_by_driver" | "completed"
                      }
                    />
                  </div>
                  {b.passengerRating != null && b.passengerRating > 0 ? (
                    <div className="text-[13px] text-muted-foreground flex items-center gap-1">
                      <Star className="size-4 fill-brand text-brand" strokeWidth={0} />
                      {b.passengerRating.toFixed(1)}
                    </div>
                  ) : (
                    <div className="text-[13px] text-muted-foreground">Нет оценок</div>
                  )}
                  {b.status === "active" ? (
                    <button
                      type="button"
                      disabled={rejectMut.isPending}
                      onClick={() => rejectMut.mutate(b.bookingId)}
                      className="mt-3 text-sm text-destructive"
                    >
                      Отклонить бронь
                    </button>
                  ) : null}
                </Card>
              ))}
            </div>
          )}
        </Section>
      </Screen>
    );
  }

  if (tripsQ.isError) {
    return (
      <Screen>
        <ScreenHeader title="Управление" />
        <Section>
          <EmptyState title="Не удалось загрузить поездки" description="Попробуйте обновить экран." />
        </Section>
      </Screen>
    );
  }

  const trips = (tripsQ.data?.trips ?? []).map((t) =>
    apiTripToCard({
      ...t,
      driverName: t.driverName ?? user?.name,
      driverRating: t.driverRating ?? user?.ratingAvg ?? 0,
    }),
  );
  const rawTrips = tripsQ.data?.trips ?? [];

  return (
    <Screen>
      <ScreenHeader title="Управление" subtitle="Твои поездки" />
      <Section title="Фильтр пассажиров">
        <Card className="!p-4">
          <div className="flex items-center gap-3 mb-3">
            <Filter className="size-4" />
            <div>
              <div className="font-semibold">Порог рейтинга</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {threshold === "off"
                  ? "Выключен — бронируют все пассажиры"
                  : `Не ниже ${threshold} (если есть оценки)`}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {THRESHOLDS.map((t) => (
              <Chip
                key={t}
                active={threshold === t}
                onClick={() => {
                  haptic("selection");
                  thresholdMut.mutate(t);
                }}
              >
                {t === "off" ? "Выключить" : `Не ниже ${t}`}
              </Chip>
            ))}
          </div>
        </Card>
      </Section>
      <Section title="Поездки">
        {tripsQ.isLoading ? (
          <div className="h-32 bg-secondary animate-pulse rounded-xl" />
        ) : trips.length === 0 ? (
          <EmptyState title="Нет поездок" description="Создайте первую поездку." />
        ) : (
          <div className="space-y-4">
            {trips.map((t, i) => (
              <div key={t.id}>
                <TripCard trip={t} onClick={() => navigate({ to: "/trip/$id", params: { id: t.id } })} />
                {tripHasRouteCoords(rawTrips[i]!) ? (
                  <YandexRouteCard target={rawTrips[i]!} className="mt-2 px-5" />
                ) : null}
                <div className="mt-2 flex flex-wrap gap-4 px-5">
                  <button
                    type="button"
                    onClick={() => setBookingsTripId(Number(t.id))}
                    className="inline-flex items-center gap-1.5 text-sm text-primary font-medium"
                  >
                    <Users className="size-4" /> Брони
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmCancel(Number(t.id))}
                    className="text-sm text-destructive"
                  >
                    Отменить поездку
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </Screen>
  );
}
