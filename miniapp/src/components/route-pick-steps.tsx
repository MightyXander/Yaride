import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Map as MapIcon, MapPin, Navigation } from "lucide-react";
import { Card, ListGroup, ListRow, NavBreadcrumbs, ScreenHeader, Section } from "@/components/ui-kit";
import { api } from "@/lib/api";
import { stopsQueryOptions } from "@/lib/queries";

export function DistrictStep({
  title,
  subtitle,
  districts,
  loading,
  showGeo,
  onMap,
  onGeo,
  onPick,
  crumbs,
}: {
  title: string;
  subtitle: string;
  districts: string[];
  loading?: boolean;
  showGeo?: boolean;
  onMap?: () => void;
  onGeo?: () => void;
  onPick: (district: string) => void;
  crumbs: string[];
}) {
  return (
    <>
      <ScreenHeader title={title} subtitle={subtitle} />
      <NavBreadcrumbs items={crumbs} />
      {onMap ? (
        <Section>
          <Card onClick={onMap} className="!p-4">
            <div className="flex items-center gap-3">
              <div className="size-11 rounded-2xl brand-gradient grid place-items-center text-[#18170f]">
                <MapIcon className="size-5" />
              </div>
              <div>
                <div className="font-semibold">На карте</div>
                <div className="text-xs text-muted-foreground">Остановки из каталога Yaride</div>
              </div>
            </div>
          </Card>
        </Section>
      ) : null}
      {showGeo && onGeo ? (
        <Section>
          <Card onClick={onGeo} className="!p-4">
            <div className="flex items-center gap-3">
              <Navigation className="size-5 text-primary" />
              <div>
                <div className="font-semibold">Отправить геолокацию</div>
                <div className="text-xs text-muted-foreground">Найдём ближайшие остановки</div>
              </div>
            </div>
          </Card>
        </Section>
      ) : null}
      <Section title={onMap ? "Или выберите район" : "Районы"}>
        {loading ? (
          <div className="h-32 rounded-xl bg-secondary animate-pulse" />
        ) : (
          <ListGroup>
            {districts.map((d) => (
              <ListRow key={d} icon={<MapPin className="size-4" />} title={d} onClick={() => onPick(d)} />
            ))}
          </ListGroup>
        )}
      </Section>
    </>
  );
}

export function StopStep({
  district,
  title,
  crumbs,
  onPick,
}: {
  district: string;
  title: string;
  crumbs: string[];
  onPick: (id: number, label: string) => void;
}) {
  const stopsQ = useQuery(stopsQueryOptions(district));
  const grouped = useMemo(() => {
    const byArea = new Map<string, { id: number; title: string; adminArea: string }[]>();
    for (const s of stopsQ.data?.stops ?? []) {
      const aa = s.adminArea || "Район";
      if (!byArea.has(aa)) byArea.set(aa, []);
      byArea.get(aa)!.push(s);
    }
    return [...byArea.entries()];
  }, [stopsQ.data]);

  return (
    <>
      <ScreenHeader title={title} subtitle={district} />
      <NavBreadcrumbs items={crumbs} />
      {stopsQ.isError ? (
        <Section>
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            Не удалось загрузить остановки. Проверьте соединение и попробуйте снова.
          </div>
          <button
            type="button"
            onClick={() => void stopsQ.refetch()}
            className="mt-3 h-11 w-full rounded-xl bg-secondary text-secondary-foreground font-semibold press"
          >
            Повторить
          </button>
        </Section>
      ) : stopsQ.isLoading ? (
        <Section>
          <div className="h-40 bg-secondary animate-pulse rounded-xl" />
        </Section>
      ) : grouped.length === 0 ? (
        <Section>
          <p className="text-sm text-muted-foreground px-1">В этом районе пока нет остановок в каталоге.</p>
        </Section>
      ) : (
        grouped.map(([aa, stops]) => (
          <Section key={aa} title={grouped.length > 1 ? aa : "Остановки"}>
            <ListGroup>
              {stops.map((s) => (
                <ListRow key={s.id} title={s.title} onClick={() => onPick(s.id, s.title)} />
              ))}
            </ListGroup>
          </Section>
        ))
      )}
    </>
  );
}

export function GeoStep({ onPick, onManual }: { onPick: (id: number, label: string) => void; onManual: () => void }) {
  const [loading, setLoading] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [nearby, setNearby] = useState<
    { id: number; title: string; district?: string; distanceKm: number }[]
  >([]);

  const loadGeo = () => {
    if (!navigator.geolocation) {
      setGeoError("Геолокация недоступна в этом браузере");
      return;
    }
    setLoading(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const res = await api.nearestStops(pos.coords.latitude, pos.coords.longitude);
          setNearby(res.stops);
        } finally {
          setLoading(false);
        }
      },
      () => {
        setLoading(false);
        setGeoError("Не удалось получить геолокацию");
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  return (
    <>
      <ScreenHeader title="Ближайшие остановки" subtitle="По прямой от вас" />
      <Section>
        <button
          onClick={loadGeo}
          disabled={loading}
          className="w-full h-12 rounded-xl brand-gradient font-bold"
        >
          {loading ? "Определяем…" : "Показать ближайшие"}
        </button>
        {geoError ? (
          <p className="mt-2 text-sm text-destructive px-1">{geoError}</p>
        ) : null}
      </Section>
      {nearby.length > 0 ? (
        <Section title="Топ-5">
          <ListGroup>
            {nearby.map((s) => (
              <ListRow
                key={s.id}
                title={s.title}
                subtitle={`${s.district ?? ""} · ~${s.distanceKm} км`}
                onClick={() => onPick(s.id, s.title)}
              />
            ))}
          </ListGroup>
        </Section>
      ) : null}
      <Section>
        <button onClick={onManual} className="w-full h-12 rounded-xl bg-secondary text-secondary-foreground font-medium">
          Выбрать вручную
        </button>
      </Section>
    </>
  );
}

export function RouteDateStep({
  onPick,
  title = "Когда едем",
  subtitle = "Выбери дату",
  showMonthNav = false,
  showWeekdayHeaders = false,
  highlightToday = false,
}: {
  onPick: (date: string) => void;
  title?: string;
  subtitle?: string;
  showMonthNav?: boolean;
  showWeekdayHeaders?: boolean;
  highlightToday?: boolean;
}) {
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const monthLabel = new Date(year, month, 1).toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  const firstDay = new Date(year, month, 1);
  const startWeekday = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  const todayKey = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();

  const monthHeader = showMonthNav ? (
    <div className="flex items-center justify-between mb-4">
      <button
        type="button"
        onClick={() => {
          const m = month - 1;
          if (m < 0) {
            setMonth(11);
            setYear(year - 1);
          } else setMonth(m);
        }}
        className="h-9 px-3 rounded-lg bg-secondary text-secondary-foreground"
      >
        ‹
      </button>
      <span className="font-semibold capitalize">{monthLabel}</span>
      <button
        type="button"
        onClick={() => {
          const m = month + 1;
          if (m > 11) {
            setMonth(0);
            setYear(year + 1);
          } else setMonth(m);
        }}
        className="h-9 px-3 rounded-lg bg-secondary text-secondary-foreground"
      >
        ›
      </button>
    </div>
  ) : (
    <div className="font-semibold capitalize mb-4">{monthLabel}</div>
  );

  return (
    <>
      <ScreenHeader title={title} subtitle={subtitle} />
      <Section>
        <Card className="!p-4">
          {monthHeader}
          {showWeekdayHeaders ? (
            <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground mb-2">
              {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((d) => (
                <div key={d}>{d}</div>
              ))}
            </div>
          ) : null}
          <div className="grid grid-cols-7 gap-1">
            {cells.map((d, i) => {
              if (d === null) return <div key={i} />;
              const cellKey = new Date(year, month, d).getTime();
              const past = cellKey < todayKey;
              const isToday = highlightToday && cellKey === todayKey;
              return (
                <button
                  key={i}
                  type="button"
                  disabled={past}
                  onClick={() =>
                    onPick(`${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`)
                  }
                  className={`h-10 rounded-lg text-sm font-medium ${
                    past
                      ? "text-muted-foreground/50"
                      : isToday
                        ? "ring-1 ring-brand bg-secondary text-foreground"
                        : "text-foreground hover:bg-secondary active:bg-secondary"
                  }`}
                >
                  {d}
                </button>
              );
            })}
          </div>
        </Card>
        <button
          onClick={() => {
            const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
            onPick(iso);
          }}
          className="mt-3 w-full h-12 rounded-xl bg-secondary text-secondary-foreground font-medium inline-flex items-center justify-center gap-2"
        >
          <CalendarDays className="size-4" /> Сегодня
        </button>
      </Section>
    </>
  );
}
