import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bell, Car, Settings2, Star, X } from "lucide-react";
import { Card, EmptyState, Screen, ScreenHeader, Section } from "@/components/ui-kit";
import type { ApiNotification } from "@/lib/api";
import { notificationsQueryOptions } from "@/lib/queries";
import { useBackButton } from "@/lib/telegram";

export const Route = createFileRoute("/notifications")({
  component: NotificationsScreen,
});

const ICONS = {
  booking: Car,
  rating: Star,
  cancel: X,
  system: Settings2,
} as const;

function formatRelativeTime(raw: string) {
  if (!raw) return "";
  const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
  const ts = Date.parse(normalized);
  if (Number.isNaN(ts)) return raw;
  const diffMs = Date.now() - ts;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "только что";
  if (mins < 60) return `${mins} мин назад`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "вчера";
  if (days < 7) return `${days} дн назад`;
  return new Date(ts).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function notificationAction(n: ApiNotification) {
  if (n.action === "rate" && n.tripId) return { to: "/rate/$id" as const, params: { id: String(n.tripId) } };
  if (n.action === "manage") return { to: "/manage" as const };
  if (n.action === "bookings") return { to: "/bookings" as const };
  if (n.tripId) return { to: "/trip/$id" as const, params: { id: String(n.tripId) } };
  return null;
}

function NotificationsScreen() {
  const navigate = useNavigate();
  useBackButton(() => navigate({ to: "/home" }));
  const notifQ = useQuery(notificationsQueryOptions());
  const items = notifQ.data?.notifications ?? [];
  const unread = items.filter((i) => i.unread).length;

  return (
    <Screen>
      <ScreenHeader
        title="Уведомления"
        subtitle={
          notifQ.isLoading
            ? "Загрузка…"
            : unread
              ? `${unread} новых`
              : items.length
                ? "Все прочитано"
                : "Пока пусто"
        }
      />
      <Section>
        {notifQ.isError ? (
          <EmptyState
            title="Не удалось загрузить"
            description="Попробуйте обновить экран."
            action={
              <button
                type="button"
                onClick={() => notifQ.refetch()}
                className="h-11 px-5 rounded-xl brand-gradient text-[#18170f] font-bold"
              >
                Повторить
              </button>
            }
          />
        ) : notifQ.isLoading ? (
          <div className="h-32 bg-secondary animate-pulse rounded-xl" />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Bell className="size-7" />}
            title="Нет уведомлений"
            description="Здесь появятся брони, отмены и напоминания об оценках."
          />
        ) : (
          <div className="space-y-3">
            {items.map((n) => {
              const Icon = ICONS[n.kind];
              const action = notificationAction(n);
              return (
                <Card
                  key={n.id}
                  className="!p-4"
                  onClick={action ? () => navigate(action) : undefined}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`size-10 rounded-full grid place-items-center shrink-0 ${
                        n.kind === "cancel"
                          ? "bg-destructive/15 text-destructive"
                          : n.kind === "rating"
                            ? "bg-brand/15 text-brand"
                            : "bg-accent text-accent-foreground"
                      }`}
                    >
                      <Icon className="size-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="text-[15px] font-semibold leading-tight">{n.title}</div>
                        {n.unread ? (
                          <span className="size-2 rounded-full bg-brand" aria-label="Не прочитано" />
                        ) : null}
                      </div>
                      <p className="text-[13px] text-muted-foreground mt-1 leading-snug">{n.body}</p>
                      <div className="text-[11px] text-muted-foreground mt-2 uppercase tracking-wider">
                        {formatRelativeTime(n.occurredAt)}
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </Section>
    </Screen>
  );
}
