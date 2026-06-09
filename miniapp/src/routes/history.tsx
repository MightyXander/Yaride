import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Star } from "lucide-react";
import {
  Card,
  EmptyState,
  Screen,
  ScreenHeader,
  Section,
  StatusBadge,
} from "@/components/ui-kit";
import type { ApiHistoryDriver, ApiHistoryPassenger } from "@/lib/api";
import { driverHistoryBadgeStatus, passengerHistoryBadgeStatus } from "@/lib/booking-status";
import { historyQueryOptions, meQueryOptions } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/history")({
  component: HistoryScreen,
});

function HistoryScreen() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const meQ = useQuery(meQueryOptions());
  const role = meQ.data?.user?.role === "driver" ? "driver" : "passenger";
  const historyQ = useQuery(historyQueryOptions(role));

  useBackButton(() => navigate({ to: "/home" }));

  const items = historyQ.data?.items ?? [];

  if (historyQ.isLoading) {
    return (
      <Screen>
        <ScreenHeader title="История" />
        <Section>
          <div className="h-32 bg-secondary animate-pulse rounded-xl" />
        </Section>
      </Screen>
    );
  }

  if (items.length === 0) {
    return (
      <Screen>
        <ScreenHeader title="История поездок" />
        <EmptyState title="История пуста" description="Завершённые поездки появятся здесь." />
      </Screen>
    );
  }

  return (
    <Screen>
      <ScreenHeader title="История поездок" subtitle={`Всего: ${items.length}`} />
      <Section>
        <div className="space-y-3">
          {role === "passenger"
            ? (items as ApiHistoryPassenger[]).map((item) => (
                <Card key={item.bookingId} className="!p-4">
                  <div className="flex items-center justify-between mb-3">
                    <StatusBadge status={passengerHistoryBadgeStatus(item)} />
                  </div>
                  <div className="text-[15px] font-semibold">
                    {item.fromTitle} → {item.toTitle}
                  </div>
                  <div className="text-[12px] text-muted-foreground mt-1">{item.whenLabel}</div>
                  <div className="mt-3 pt-3 hairline-t flex items-center justify-between">
                    {item.myRatingStars ? (
                      <span className="text-[13px] text-muted-foreground flex items-center gap-1">
                        <Star className="size-4 fill-brand text-brand" strokeWidth={0} />
                        Ваша оценка: {item.myRatingStars}
                      </span>
                    ) : item.canRate ? (
                      <button
                        onClick={() => {
                          haptic("light");
                          navigate({ to: "/rate/$id", params: { id: String(item.tripId) } });
                        }}
                        className="h-9 px-4 rounded-xl brand-gradient text-[#18170f] text-[13px] font-bold"
                      >
                        Оценить
                      </button>
                    ) : (
                      <span className="text-[13px] text-muted-foreground">Оценка недоступна</span>
                    )}
                  </div>
                </Card>
              ))
            : (items as ApiHistoryDriver[]).map((item) => (
                <Card key={item.tripId} className="!p-4">
                  <div className="flex items-center justify-between mb-3">
                    <StatusBadge status={driverHistoryBadgeStatus(item)} />
                  </div>
                  <div className="text-[15px] font-semibold">
                    {item.fromTitle} → {item.toTitle}
                  </div>
                  <div className="text-[12px] text-muted-foreground mt-1">{item.whenLabel}</div>
                </Card>
              ))}
        </div>
      </Section>
    </Screen>
  );
}
