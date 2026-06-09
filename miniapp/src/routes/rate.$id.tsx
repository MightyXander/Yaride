import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  BottomCTA,
  Card,
  Chip,
  RatingStars,
  Screen,
  ScreenHeader,
  Section,
} from "@/components/ui-kit";
import { api, ApiError } from "@/lib/api";
import { queryKeys, ratingsPendingQueryOptions, tripQueryOptions } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/rate/$id")({
  component: RateScreen,
});

const TAGS = ["Пунктуально", "Чистая машина", "Спокойная езда", "Приятное общение", "Безопасно"];

function RateScreen() {
  const { id } = Route.useParams();
  const tripId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const tripQ = useQuery(tripQueryOptions(tripId));
  const pendingQ = useQuery(ratingsPendingQueryOptions());

  const [step, setStep] = useState<1 | 2>(1);
  const [value, setValue] = useState(0);
  const [comment, setComment] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const pending = useMemo(
    () => pendingQ.data?.pending.find((p) => p.tripId === tripId),
    [pendingQ.data, tripId],
  );

  const rateMut = useMutation({
    mutationFn: () =>
      api.submitRating({
        trip_id: tripId,
        rated_tg_user_id: pending!.ratedTgUserId,
        stars: value,
        review_text: [...tags, comment.trim()].filter(Boolean).join(". ") || undefined,
      }),
    onSuccess: async () => {
      haptic("success");
      await queryClient.invalidateQueries({ queryKey: queryKeys.history("passenger") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.ratingsPending });
      navigate({ to: "/history" });
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Ошибка"),
  });

  useBackButton(() => navigate({ to: "/history" }));

  const trip = tripQ.data;

  if (tripQ.isLoading || pendingQ.isLoading) {
    return (
      <Screen>
        <ScreenHeader title="Загрузка…" />
      </Screen>
    );
  }

  if (!trip || !pending) {
    return (
      <Screen>
        <ScreenHeader title="Оценка недоступна" subtitle="Поездка не найдена или окно оценки закрыто" />
      </Screen>
    );
  }

  if (step === 1) {
    return (
      <Screen>
        <ScreenHeader title="Как поездка?" subtitle="Шаг 1 из 2" />
        <Section>
          <Card className="!p-5 text-center">
            <div className="text-[17px] font-bold">{pending.ratedName}</div>
            <div className="text-[12px] text-muted-foreground mt-1">
              {trip.fromTitle} → {trip.toTitle}
            </div>
            <div className="mt-6 flex justify-center">
              <RatingStars value={value} size={36} onChange={(v) => { haptic("selection"); setValue(v); }} />
            </div>
          </Card>
        </Section>
        {error ? <div className="mx-5 text-sm text-destructive">{error}</div> : null}
        <BottomCTA text="Далее" disabled={value < 1} onClick={() => setStep(2)} />
      </Screen>
    );
  }

  return (
    <Screen>
      <ScreenHeader title="Комментарий" subtitle="Шаг 2 из 2 · необязательно" />
      <Section>
        <div className="flex flex-wrap gap-2">
          {TAGS.map((t) => (
            <Chip key={t} active={tags.includes(t)} onClick={() => setTags((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))}>
              {t}
            </Chip>
          ))}
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={4}
          placeholder="Ещё пара слов…"
          className="mt-4 w-full p-4 rounded-2xl bg-input/60 outline-none resize-none"
        />
      </Section>
      <BottomCTA text="Отправить оценку" onClick={() => rateMut.mutate()} disabled={rateMut.isPending} />
    </Screen>
  );
}
