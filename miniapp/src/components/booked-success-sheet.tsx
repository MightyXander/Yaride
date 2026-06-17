import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, MessageCircle } from "lucide-react";
import { YandexRouteCard } from "@/components/yandex-route-card";
import { tripQueryOptions } from "@/lib/queries";
import { useTelegram } from "@/lib/telegram";

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
  const { openExternal } = useTelegram();
  const [closing, setClosing] = useState(false);

  const close = useCallback(() => {
    if (closing) return;
    setClosing(true);
    window.setTimeout(onClose, 220);
  }, [closing, onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  return (
    <div className="fixed inset-0 z-[60] grid place-items-end">
      <div
        data-closing={closing}
        className="sheet-backdrop absolute inset-0 bg-foreground/40 backdrop-blur-[2px]"
      />
      <button
        type="button"
        className="absolute inset-0"
        aria-label="Закрыть"
        onClick={close}
      />
      <div
        data-closing={closing}
        role="dialog"
        aria-modal="true"
        className="sheet-panel relative w-full bg-card text-card-foreground rounded-t-3xl px-5 pt-3 pb-[calc(env(safe-area-inset-bottom)+20px)] shadow-[0_-20px_60px_-20px_rgba(0,0,0,0.5)]"
      >
        <div className="sheet-handle" aria-hidden />
        <div className="mx-auto mb-3 size-14 rounded-full brand-gradient brand-glow grid place-items-center animate-pop">
          <Check className="size-7" strokeWidth={3} />
        </div>
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
        {tripQ.data?.driverUsername ? (
          <button
            type="button"
            onClick={() => {
              if (tripQ.data?.driverUsername) {
                window.open(`https://t.me/${tripQ.data.driverUsername}`, "_blank");
              }
            }}
            className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold press flex items-center justify-center gap-2 mt-4"
          >
            <MessageCircle className="size-4" />
            Написать водителю
          </button>
        ) : null}
        <p className="text-sm text-muted-foreground text-center mt-4">Добавить маршрут в избранное?</p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={close}
            className="h-12 rounded-xl bg-secondary text-secondary-foreground font-semibold press"
          >
            Нет
          </button>
          <button
            type="button"
            onClick={() => void onAddFavorite()}
            className="h-12 rounded-xl brand-gradient brand-glow text-[#18170f] font-bold press"
          >
            Добавить
          </button>
        </div>
        {tripQ.data?.driverUsername ? (
          <button
            type="button"
            onClick={() => openExternal(`https://t.me/${tripQ.data.driverUsername}`)}
            className="mt-3 w-full h-12 rounded-xl brand-gradient brand-glow text-[#18170f] font-bold flex items-center justify-center gap-2 press"
          >
            <MessageCircle className="size-4" />
            Написать водителю
          </button>
        ) : null}
      </div>
    </div>
  );
}
