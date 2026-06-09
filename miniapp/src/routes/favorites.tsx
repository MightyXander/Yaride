import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, Trash2 } from "lucide-react";
import { Card, EmptyState, Screen, ScreenHeader, Section } from "@/components/ui-kit";
import { api } from "@/lib/api";
import { favoritesQueryOptions, queryKeys } from "@/lib/queries";
import { useBackButton } from "@/lib/telegram";

export const Route = createFileRoute("/favorites")({
  component: FavoritesScreen,
});

function FavoritesScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const favQ = useQuery(favoritesQueryOptions());

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteFavorite(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.favorites }),
  });

  useBackButton(() => navigate({ to: "/home" }));

  const items = favQ.data?.favorites ?? [];

  return (
    <Screen>
      <ScreenHeader title="Избранные маршруты" subtitle={items.length ? `Сохранено: ${items.length}` : undefined} />
      {favQ.isLoading ? (
        <Section>
          <div className="h-32 bg-secondary animate-pulse rounded-xl" />
        </Section>
      ) : items.length === 0 ? (
        <EmptyState title="Избранного пока нет" description="Добавьте маршрут после бронирования." />
      ) : (
        <Section>
          <div className="space-y-3">
            {items.map((f) => (
              <Card key={f.id} className="!p-4">
                <button
                  onClick={() =>
                    navigate({
                      to: "/search",
                      search: {
                        fromPointId: f.startPointId,
                        toPointId: f.endPointId,
                        fromLabel: f.fromTitle,
                        toLabel: f.toTitle,
                      },
                    })
                  }
                  className="w-full text-left flex items-start gap-3"
                >
                  <div className="size-10 rounded-2xl bg-brand/15 text-brand grid place-items-center">
                    <Star className="size-5 fill-brand" strokeWidth={0} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[15px] font-semibold truncate">
                      {f.fromTitle} → {f.toTitle}
                    </div>
                  </div>
                </button>
                <button
                  onClick={() => deleteMut.mutate(f.id)}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground"
                >
                  <Trash2 className="size-3.5" /> Убрать
                </button>
              </Card>
            ))}
          </div>
        </Section>
      )}
    </Screen>
  );
}
