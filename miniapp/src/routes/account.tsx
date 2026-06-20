import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, IdCard, RefreshCw, UserRound } from "lucide-react";
import { Card, ListGroup, ListRow, RatingStars, Screen, ScreenHeader, Section } from "@/components/ui-kit";
import { meQueryOptions, ratingsReceivedQueryOptions } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { Monitor, Moon, Palette, Sun } from "lucide-react";

export const Route = createFileRoute("/account")({
  component: AccountScreen,
});

function AccountScreen() {
  const navigate = useNavigate();
  const { user: tgUser, haptic } = useTelegram();
  const { mode, resolved, setMode } = useTheme();
  const meQ = useQuery(meQueryOptions());
  const ratingsQ = useQuery(ratingsReceivedQueryOptions());

  useBackButton(() => navigate({ to: "/home" }));

  if (meQ.isLoading) {
    return (
      <Screen>
        <ScreenHeader title="Профиль" />
        <Section>
          <div className="h-40 bg-secondary animate-pulse rounded-xl" />
        </Section>
      </Screen>
    );
  }

  if (meQ.isError || !meQ.data?.registered || !meQ.data.user) {
    return (
      <Screen>
        <ScreenHeader title="Профиль" />
        <Section>
          <button onClick={() => void meQ.refetch()} className="w-full h-12 rounded-xl brand-gradient font-bold inline-flex items-center justify-center gap-2">
            <RefreshCw className="size-4" /> Повторить
          </button>
        </Section>
      </Screen>
    );
  }

  const profile = meQ.data.user;
  const isDriver = profile.role === "driver";
  const ratings = ratingsQ.data?.ratings ?? [];

  return (
    <Screen>
      <ScreenHeader title="Профиль" />
      <div className="list-stagger">
      <Section>
        <Card className="!p-5">
          <div className="flex items-center gap-4">
            <div className="size-16 rounded-full brand-gradient grid place-items-center text-[22px] font-extrabold">
              {profile.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <div className="text-[18px] font-bold">{profile.name}</div>
              <div className="text-[13px] text-muted-foreground">{tgUser?.username ? `@${tgUser.username}` : "Telegram"}</div>
            </div>
          </div>
          <div className="mt-5 pt-5 hairline-t flex items-center justify-between">
            <div>
              <div className="text-[26px] font-extrabold">{profile.ratingCount ? profile.ratingAvg.toFixed(1) : "—"}</div>
              <div className="text-xs text-muted-foreground">{profile.ratingCount ? `${profile.ratingCount} оценок` : "нет оценок"}</div>
            </div>
            <RatingStars value={profile.ratingAvg} size={22} />
          </div>
        </Card>
      </Section>

      <Section title="Данные">
        <ListGroup>
          <ListRow icon={<UserRound className="size-4" />} title="Имя" trailing={profile.name} />
          {profile.dlSeriesNumber ? (
            <ListRow icon={<IdCard className="size-4" />} title="ВУ" trailing={profile.dlSeriesNumber} />
          ) : null}
          <ListRow
            icon={<IdCard className="size-4" />}
            title={profile.dlSeriesNumber ? "Обновить ВУ" : "Добавить ВУ"}
            onClick={() => navigate({ to: "/license" })}
            trailing={<ChevronRight className="size-4" />}
          />
        </ListGroup>
      </Section>

      {ratings.length > 0 ? (
        <Section title="Отзывы">
          <div className="space-y-2">
            {ratings.slice(0, 5).map((r, i) => (
              <Card key={i} className="!p-3">
                <div className="flex items-center gap-2">
                  <RatingStars value={r.stars} size={16} />
                  <span className="text-sm font-medium">{r.fromName}</span>
                </div>
                {r.reviewText ? <p className="text-xs text-muted-foreground mt-1">{r.reviewText}</p> : null}
              </Card>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="Оформление">
        <Card className="!p-4">
          <div className="flex items-center gap-3 mb-3">
            <Palette className="size-4" />
            <span className="font-semibold">Тема</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(
              [
                { id: "system" as ThemeMode, label: "Авто", Icon: Monitor },
                { id: "light" as ThemeMode, label: "Светлая", Icon: Sun },
                { id: "dark" as ThemeMode, label: "Тёмная", Icon: Moon },
              ] as const
            ).map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => {
                  setMode(id);
                  haptic("selection");
                }}
                className={`h-12 rounded-xl flex flex-col items-center justify-center gap-0.5 text-[11px] font-semibold ${
                  mode === id ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"
                }`}
              >
                <Icon className="size-4" />
                {label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground mt-2">Сейчас: {resolved === "dark" ? "тёмная" : "светлая"}</p>
        </Card>
      </Section>
      </div>
    </Screen>
  );
}
