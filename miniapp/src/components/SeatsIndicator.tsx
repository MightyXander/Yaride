import { Icon } from "./Icon";

interface SeatsIndicatorProps {
  total: number;
  free: number;
}

// Ряд иконок-человечков: занятые места — серые (outline), свободные — primary.
export function SeatsIndicator({ total, free }: SeatsIndicatorProps) {
  const taken = total - free;
  return (
    <div className="flex gap-1">
      {Array.from({ length: total }).map((_, i) => {
        const isFree = i >= taken;
        return (
          <Icon
            key={i}
            name="person"
            filled={isFree}
            className={`text-[18px] ${isFree ? "text-primary" : "text-outline-variant"}`}
          />
        );
      })}
    </div>
  );
}
