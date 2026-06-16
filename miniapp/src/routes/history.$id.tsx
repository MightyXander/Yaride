import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { Shield, Users } from "lucide-react";
import { YandexRouteCard } from "@/components/yandex-route-card";
import { BottomCTA, Card, Screen, ScreenHeader, Section, StatusBadge } from "@/components/ui-kit";
import type { ApiHistoryDriver, ApiHistoryPassenger } from "@/lib/api";
import { driverHistoryBadgeStatus, passengerHistoryBadgeStatus } from "@/lib/booking-status";
import { historyQueryOptions, meQueryOptions, tripQueryOptions } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/history/$id")({
  component: HistoryDetailScreen,
});

/** Читаемый лейбл статуса поездки для истории. */
function tripStatusLabel(status?: string): string {
  if (status === "completed") return "Завершена";
  if (status === "cancelled") return "Отменена";
  return "Прошла";
}

function HistoryDetailScreen() {
  const { id } = Route.useParams();
  const tripId = Number(id);
  const navigate = useNavigate();
  const { haptic } = useTelegram();

  const meQ = useQuery(meQueryOptions());
  const role = meQ.data?.user?.role === "driver" ? "driver" : "passenger";
  const historyQ = useQuery(historyQueryOptions(role));
  const tripQ = useQuery(tripQueryOptions(tripId));

  useBackButton(() => navigate({ to: "/history" }));

  const items = historyQ.data?.items ?? [];
  const passengerItem =
    role === "passenger"
      ? (items as ApiHistoryPassenger[]).find((i) => i.tripId === tripId)
      : undefined;
  const driverItem =
    role === "driver" ? (items as ApiHistoryDriver[]).find((i) => i.tripId === tripId) : undefined;

  if (tripQ.isLoading || historyQ.isLoading || meQ.isLoading) {
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

  // seatsBooked отсутствует в карточке деталей — считаем из общего/свободного.
  const seatsBooked = driverItem?.seatsBooked ?? Math.max(0, trip.seatsTotal - trip.seatsFree);
  const tripStatus = trip.status ?? driverItem?.tripStatus ?? passengerItem?.tripStatus;
  const cancelReason = passengerItem?.cancelReason;
  const car = [trip.carModel, trip.carColor, trip.carPlate].filter(Boolean).join(", ");

  return (
    <Screen>
      <ScreenHeader title="Детали поездки" subtitle={`№ ${trip.id}`} />
      <div className="list-stagger">
        {role === "passenger" ? (
          <Section>
            <Card className="!p-5">
              <div className="flex items-center gap-3">
                <div className="size-14 rounded-full brand-gradient grid place-items-center text-[18px] font-extrabold text-[#18170f]">
                  {(trip.driverName ?? "В").charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[17px] font-bold truncate">{trip.driverName}</div>
                  <div className="text-[12px] text-muted-foreground flex items-center gap-1.5">
                    <Shield className="size-3.5 text-success" />★ {trip.driverRating.toFixed(1)}
                    {trip.driverTripsCount ? ` · ${trip.driverTripsCount} поездок` : ""}
                  </div>
                </div>
              </div>
            </Card>
          </Section>
        ) : null}

        <Section title="Маршрут">
          <Card className="!p-5">
            <div className="text-[16px] font-semibold">{trip.fromTitle}</div>
            <div className="text-muted-foreground my-2">↓</div>
            <div className="text-[16px] font-semibold">{trip.toTitle}</div>
            <div className="mt-4 text-sm text-muted-foreground">{trip.whenLabel}</div>
          </Card>
          <YandexRouteCard target={trip} className="mt-3" />
        </Section>

        <Section title="Поездка">
          <ListRowInline label="Статус поездки" value={tripStatusLabel(tripStatus)} />
          {passengerItem ? (
            <div className="flex items-center justify-between py-3 hairline-b last:border-0">
              <span className="text-sm text-muted-foreground">Статус брони</span>
              <StatusBadge status={passengerHistoryBadgeStatus(passengerItem)} />
            </div>
          ) : driverItem ? (
            <div className="flex items-center justify-between py-3 hairline-b last:border-0">
              <span className="text-sm text-muted-foreground">Статус</span>
              <StatusBadge status={driverHistoryBadgeStatus(driverItem)} />
            </div>
          ) : null}
          <ListRowInline
            icon={<Users className="size-4" />}
            label="Занято мест"
            value={`${seatsBooked} / ${trip.seatsTotal}`}
          />
          <ListRowInline label="Цена за место" value={`${trip.priceRub} ₽`} />
          {role === "passenger" && car ? <ListRowInline label="Авто" value={car} /> : null}
          {cancelReason ? <ListRowInline label="Причина отмены" value={cancelReason} /> : null}
        </Section>

        {trip.comment ? (
          <Section title="Комментарий водителя">
            <Card className="!p-5 text-[15px] leading-relaxed">{trip.comment}</Card>
          </Section>
        ) : null}
      </div>

      <BottomCTA
        forceInPage
        visible={!!passengerItem?.canRate}
        text="Оценить"
        onClick={() => {
          haptic("light");
          navigate({ to: "/rate/$id", params: { id: String(tripId) } });
        }}
      />
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
      <span className="text-sm font-semibold text-right">{value}</span>
    </div>
  );
}
