import { Icon } from "./Icon";

interface StarRatingProps {
  value: number;
  className?: string;
}

// Компактный рейтинг: одна золотая звезда + число (★ 4.8) — паттерн из DESIGN.md.
export function StarRating({ value, className = "" }: StarRatingProps) {
  return (
    <div className={`flex items-center text-label-sm font-label-sm text-tertiary ${className}`}>
      <Icon name="star" filled className="text-[14px] mr-1" />
      {value.toFixed(1)}
    </div>
  );
}
