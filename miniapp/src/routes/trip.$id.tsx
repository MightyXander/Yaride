import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, type ReactNode } from "react";
import { MessageCircle, Shield, Users } from "lucide-react";
import { BookedSuccessSheet } from "@/components/booked-success-sheet";
import { YandexRouteCard } from "@/components/yandex-route-card";
import { BottomCTA, Card, Screen, ScreenHeader, Section } from "@/components/ui-kit";
import { api, ApiError } from "@/lib/api";
import { bookingsQueryOptions, meQueryOptions, queryKeys, tripQueryOptions } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/trip/$id")({
  validateSearch: (search: Record<string, unknown>) => ({
    autoBook: search.autoBook === true,
  }),
  component: TripDetailScreen,
});

function TripDetailScreen() {
  const { id } = Route.useParams();
  const search = Route.useSearch();
  const tripId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { haptic, openExternal } = useTelegram();
  const tripQ = useQuery(tripQueryOptions(tripId));
  const bookingsQ = useQuery(bookingsQueryOptions());
  const meQ = useQuery(meQueryOptions());
  const [bookError, setBookError] = useState<string | null>(null);
  const [booked, setBooked] = useState(false);

  const bookMut = useMutation({
    mutationFn: () => api.book(tripId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.bookings });
      await queryClient.invalidateQueries({ queryKey: queryKeys.trip(tripId) });
      haptic("success");
      setBookError(null);
      setBooked(true);
    },
    onError: (e: Error) => {
      haptic("error");
      setBookError(e instanceof ApiError ? e.message : "Не удалось забронировать");
    },
  });

  const favMut = useMutation({
    mutationFn: () => api.addFavorite({ trip_id: tripId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.favorites }),
  });

  useEffect(() => {
    if (search.autoBook && tripQ.data && meQ.data?.registered && !bookMut.isPending && !booked && !bookError) {
      const trip = tripQ.data;
      const alreadyBooked = (bookingsQ.data?.bookings ?? []).some(
        (b) => b.tripId === tripId && b.status === "active",
      );
      const canBook = trip.seatsFree > 0 && trip.status === "open" && !alreadyBooked;
      if (canBook) {
        navigate({ to: "/trip/$id", params: { id }, search: {}, replace: true });
        bookMut.mutate();
      }
    }
  }, [search.autoBook, tripQ.data, meQ.data, bookMut, bookingsQ.data, booked, bookError, tripId, id, navigate]);

  useBackButton(() => navigate({ to: "/search" }));

  if (tripQ.isLoading) {
    return (
      <Screen>
        <ScreenHeader title="Загрузка…" />
        <Section>
          <div className="h-40 bg-secondary animate-pulse rounded-xl" />
        </Section>
      </Screen>
    );
  }

  const trip = tripQ.data;
  if (!trip) {
    return (
      <Screen>
        <ScreenHeader title="Поездка не найдена" />
      </Screen>
    );
  }

  const free = trip.seatsFree;
  const alreadyBooked = (bookingsQ.data?.bookings ?? []).some(
    (b) => b.tripId === tripId && b.status === "active",
  );
  const canBook = free > 0 && trip.status === "open" && !alreadyBooked;

  return (
    <Screen>
      <ScreenHeader title="Детали поездки" subtitle={`№ ${trip.id}`} />
      <div className="list-stagger">
        <Section>
          <Card className="!p-5">
            <div className="flex items-center gap-3">
              <div className="size-14 rounded-full brand-gradient grid place-items-center text-[18px] font-extrabold">
                {(trip.driverName ?? "В").charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[17px] font-bold truncate">{trip.driverName}</div>
                <div className="text-[12px] text-muted-foreground flex items-center gap-1.5">
                  <Shield className="size-3.5 text-success" />
                  ★ {trip.driverRating.toFixed(1)}
                  {trip.driverTripsCount ? ` · ${trip.driverTripsCount} поездок` : ""}
                </div>
              </div>
            </div>
            {alreadyBooked && trip.driverUsername ? (
              <button
                type="button"
                onClick={() => openExternal(`https://t.me/${trip.driverUsername}`)}
                className="mt-3 w-full h-10 rounded-xl bg-secondary text-secondary-foreground font-semibold flex items-center justify-center gap-2 press"
              >
                <MessageCircle className="size-4" />
                Написать водителю
              </button>
            ) : null}
          </Card>
        </Section>
        <Section title="Маршрут">
          <Card className="!p-5">
            <div className="text-[16px] font-semibold">{trip.fromTitle}</div>
            <div className="text-muted-foreground my-2">↓</div>
            <div className="text-[16px] font-semibold">{trip.toTitle}</div>
            <div className="mt-4 text-sm text-muted-foreground">{trip.whenLabel}</div>
          </Card>
          <YandexRouteCard target={trip} className="mt-3" />
        </Section>
        <Section>
          <ListRowInline icon={<Users className="size-4" />} label="Свободно мест" value={`${free} / ${trip.seatsTotal}`} />
          <ListRowInline label="Цена за место" value={`${trip.priceRub} ₽`} />
          {trip.carModel ? (
            <ListRowInline label="Авто" value={[trip.carModel, trip.carColor, trip.carPlate].filter(Boolean).join(", ")} />
          ) : null}
          {trip.comment ? <ListRowInline label="Комментарий" value={trip.comment} /> : null}
        </Section>
      </div>
      {bookError ? <div className="mx-5 text-sm text-destructive animate-fade-in">{bookError}</div> : null}
      {canBook ? <div className="h-24" /> : null}
      <BottomCTA
        forceInPage
        visible={canBook}
        text="Забронировать"
        disabled={bookMut.isPending}
        onClick={() => {
          haptic("light");
          setBookError(null);
          const registered = meQ.data?.registered ?? false;
          if (!registered) {
            navigate({ to: "/onboarding", search: { pendingTripId: tripId } });
            return;
          }
          bookMut.mutate();
        }}
      />
      {booked ? (
        <BookedSuccessSheet
          tripId={tripId}
          fromLabel={trip.fromTitle}
          toLabel={trip.toTitle}
          onClose={() => {
            setBooked(false);
            navigate({ to: "/bookings" });
          }}
          onAddFavorite={async () => {
            await favMut.mutateAsync();
            haptic("success");
            setBooked(false);
            navigate({ to: "/bookings" });
          }}
        />
      ) : null}
    </Screen>
  );
}

function ListRowInline({ icon, label, value }: { icon?: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3 hairline-b last:border-0">
      <span className="text-sm text-muted-foreground flex items-center gap-2">
        {icon}
        {label}
      </span>
      <span className="text-sm font-semibold">{value}</span>
    </div>
  );
}
