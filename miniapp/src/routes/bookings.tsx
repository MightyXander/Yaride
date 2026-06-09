import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  BottomCTA,
  Card,
  EmptyState,
  Screen,
  ScreenHeader,
  Section,
  StatusBadge,
} from "@/components/ui-kit";
import { YandexRouteCard } from "@/components/yandex-route-card";
import { api } from "@/lib/api";
import { bookingsQueryOptions, queryKeys } from "@/lib/queries";
import { useBackButton, useMainButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/bookings")({
  component: BookingsScreen,
});

function CancelScreen({
  bookingId,
  onDone,
  onBack,
}: {
  bookingId: number;
  onDone: () => void;
  onBack: () => void;
}) {
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const [reason, setReason] = useState("");
  const canCancel = reason.trim().length >= 3;

  const cancelMut = useMutation({
    mutationFn: () => api.cancelBooking(bookingId, reason.trim()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.bookings });
      haptic("warning");
      onDone();
    },
  });

  useMainButton("Отменить бронь", () => cancelMut.mutate(), { enabled: canCancel });
  useBackButton(onBack);

  return (
    <Screen>
      <ScreenHeader title="Отмена брони" subtitle="Причина уйдёт водителю" />
      <Section>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={5}
          placeholder="Минимум 3 символа"
          className="w-full p-4 rounded-2xl bg-input/60 outline-none resize-none"
        />
      </Section>
      <BottomCTA text="Отменить бронь" onClick={() => cancelMut.mutate()} disabled={!canCancel} variant="destructive" />
    </Screen>
  );
}

function BookingsScreen() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const [cancelingId, setCancelingId] = useState<number | null>(null);
  const bookingsQ = useQuery(bookingsQueryOptions());

  useBackButton(() => {
    if (cancelingId) setCancelingId(null);
    else navigate({ to: "/home" });
  });

  if (cancelingId) {
    return (
      <CancelScreen
        bookingId={cancelingId}
        onDone={() => setCancelingId(null)}
        onBack={() => setCancelingId(null)}
      />
    );
  }

  const rows = bookingsQ.data?.bookings ?? [];
  const activeCount = rows.filter((r) => r.status === "active").length;

  if (bookingsQ.isLoading) {
    return (
      <Screen>
        <ScreenHeader title="Мои брони" />
        <Section>
          <div className="h-32 bg-secondary animate-pulse rounded-xl" />
        </Section>
      </Screen>
    );
  }

  if (rows.length === 0) {
    return (
      <Screen>
        <ScreenHeader title="Мои брони" />
        <EmptyState title="Броней пока нет" description="Найдите поездку в разделе «Найти»." />
      </Screen>
    );
  }

  return (
    <Screen>
      <ScreenHeader title="Мои брони" subtitle={`Активных: ${activeCount} · всего: ${rows.length}`} />
      <Section>
        <div className="space-y-3">
          {rows.map((b) => (
            <Card key={b.id} className="!p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-muted-foreground">№ {b.id}</span>
                <StatusBadge status={b.status as "active" | "cancelled_by_passenger" | "cancelled_by_driver" | "completed"} />
              </div>
              <div className="text-[16px] font-semibold">
                {b.fromTitle} → {b.toTitle}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {b.whenLabel} · {b.priceRub} ₽
              </div>
              {b.status === "active" ? <YandexRouteCard target={b} className="mt-3" /> : null}
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => {
                    haptic("light");
                    navigate({ to: "/trip/$id", params: { id: String(b.tripId) } });
                  }}
                  className="h-10 px-4 rounded-xl bg-secondary text-secondary-foreground text-sm font-semibold"
                >
                  Подробнее
                </button>
                {b.status === "active" ? (
                  <button
                    onClick={() => setCancelingId(b.id)}
                    className="h-10 px-4 rounded-xl bg-destructive/15 text-destructive text-sm font-semibold"
                  >
                    Отменить
                  </button>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      </Section>
    </Screen>
  );
}
