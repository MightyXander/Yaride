import { useQuery } from "@tanstack/react-query";
import { YandexRouteCard } from "@/components/yandex-route-card";
import { tripQueryOptions } from "@/lib/queries";

export function BookedSuccessSheet({
  tripId,
  fromLabel,
  toLabel,
  onClose,
  onAddFavorite,
}: {
  tripId: number;
  fromLabel: string;
  toLabel: string;
  onClose: () => void;
  onAddFavorite: () => void | Promise<void>;
}) {
  const tripQ = useQuery({ ...tripQueryOptions(tripId), enabled: tripId > 0 });

  return (
    <div className="fixed inset-0 z-[60] bg-foreground/30 grid place-items-end">
      <div className="w-full bg-card rounded-t-3xl p-5 pb-[calc(env(safe-area-inset-bottom)+20px)]">
        <h3 className="text-xl font-bold text-center">Бронь создана</h3>
        <p className="text-sm text-muted-foreground text-center mt-1">
          {fromLabel} → {toLabel}
        </p>
        <YandexRouteCard
          target={
            tripQ.data ?? {
              fromTitle: fromLabel,
              toTitle: toLabel,
            }
          }
          className="mt-4"
        />
        <p className="text-sm text-muted-foreground text-center mt-4">Добавить маршрут в избранное?</p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={onClose}
            className="h-12 rounded-xl bg-secondary text-secondary-foreground font-semibold"
          >
            Нет
          </button>
          <button
            type="button"
            onClick={() => void onAddFavorite()}
            className="h-12 rounded-xl bg-primary text-primary-foreground font-semibold"
          >
            Добавить
          </button>
        </div>
      </div>
    </div>
  );
}
