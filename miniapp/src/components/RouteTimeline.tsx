interface RouteTimelineProps {
  from: string;
  to: string;
  labels?: boolean;
}

// Маршрут «откуда → куда» с вертикальной линией и точками (как в карточке поездки Stitch).
// Верхняя точка — обводка primary, нижняя — закрашенная outline-variant.
export function RouteTimeline({ from, to, labels = false }: RouteTimelineProps) {
  return (
    <div className="relative flex flex-col gap-4 py-2">
      <div className="absolute left-[7px] top-3 bottom-3 w-px bg-outline-variant" />
      <div className="flex items-start gap-4">
        <div className="w-3.5 h-3.5 mt-0.5 rounded-full border-2 border-primary bg-surface z-10 shrink-0" />
        <div>
          {labels && (
            <p className="text-label-sm font-label-sm text-on-surface-variant uppercase tracking-wider">
              Откуда
            </p>
          )}
          <p className="font-body-md text-body-md text-on-surface">{from}</p>
        </div>
      </div>
      <div className="flex items-start gap-4">
        <div className="w-3.5 h-3.5 mt-0.5 rounded-full border-2 border-outline-variant bg-outline-variant z-10 shrink-0" />
        <div>
          {labels && (
            <p className="text-label-sm font-label-sm text-on-surface-variant uppercase tracking-wider">
              Куда
            </p>
          )}
          <p className="font-body-md text-body-md text-on-surface">{to}</p>
        </div>
      </div>
    </div>
  );
}
