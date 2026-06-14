import { useCallback, useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Chip } from "@/components/ui-kit";
import { TIME_SLOTS } from "@/lib/time-slots";

export type SearchTripFilters = {
  departureTime: string | null;
  minSeatsFree: number | null;
};

export const EMPTY_SEARCH_FILTERS: SearchTripFilters = {
  departureTime: null,
  minSeatsFree: null,
};

export function searchFiltersActive(filters: SearchTripFilters): boolean {
  return filters.departureTime != null || filters.minSeatsFree != null;
}

export function FilterButton({
  active,
  onClick,
}: {
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative shrink-0 size-11 rounded-2xl grid place-items-center press ${
        active ? "brand-gradient text-[#18170f]" : "bg-secondary text-secondary-foreground"
      }`}
      aria-label="Фильтр"
    >
      <SlidersHorizontal className="size-5" />
      {active ? (
        <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-destructive ring-2 ring-card" />
      ) : null}
    </button>
  );
}

export function SearchFilterSheet({
  filters,
  onApply,
  onClose,
}: {
  filters: SearchTripFilters;
  onApply: (next: SearchTripFilters) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<SearchTripFilters>(filters);
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
    <div className="fixed inset-0 z-50 grid place-items-end">
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
        className="sheet-panel relative w-full bg-card text-card-foreground rounded-t-3xl px-5 pt-3 pb-[calc(env(safe-area-inset-bottom)+20px)] max-h-[85dvh] overflow-y-auto shadow-[0_-20px_60px_-20px_rgba(0,0,0,0.5)]"
      >
        <div className="sheet-handle" aria-hidden />
        <h3 className="text-xl font-bold">Фильтр</h3>
        <p className="text-sm text-muted-foreground mt-1">Сузить список по времени и местам</p>

        <div className="mt-5">
          <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground mb-2.5">
            Время отправления
          </div>
          <div className="flex flex-wrap gap-2">
            <Chip active={draft.departureTime == null} onClick={() => setDraft((s) => ({ ...s, departureTime: null }))}>
              Любое
            </Chip>
            {TIME_SLOTS.map((t) => (
              <Chip
                key={t}
                active={draft.departureTime === t}
                onClick={() => setDraft((s) => ({ ...s, departureTime: t }))}
              >
                {t}
              </Chip>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground mb-2.5">
            Свободных мест не меньше
          </div>
          <div className="flex flex-wrap gap-2">
            <Chip active={draft.minSeatsFree == null} onClick={() => setDraft((s) => ({ ...s, minSeatsFree: null }))}>
              Любое
            </Chip>
            {[1, 2, 3, 4].map((n) => (
              <Chip
                key={n}
                active={draft.minSeatsFree === n}
                onClick={() => setDraft((s) => ({ ...s, minSeatsFree: n }))}
              >
                {n}+
              </Chip>
            ))}
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => {
              onApply(EMPTY_SEARCH_FILTERS);
              close();
            }}
            className="h-12 rounded-xl bg-secondary text-secondary-foreground font-semibold press"
          >
            Сбросить
          </button>
          <button
            type="button"
            onClick={() => {
              onApply(draft);
              close();
            }}
            className="h-12 rounded-xl brand-gradient brand-glow font-bold press"
          >
            Применить
          </button>
        </div>
      </div>
    </div>
  );
}
