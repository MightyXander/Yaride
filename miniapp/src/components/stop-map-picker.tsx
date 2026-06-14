import { Component, lazy, Suspense, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, MapPin, Navigation, Search, X } from "lucide-react";
import { Button, ScreenHeader, TextInput } from "@/components/ui-kit";
import type { ApiMapStop } from "@/lib/api";
import {
  findNearestStop,
  STOP_MAP_DEFAULT_ZOOM,
  STOP_MAP_FOCUS_ZOOM,
  STOP_MAP_ZOOM_RANGE,
  YAROSLAVL_CENTER_LNG_LAT,
} from "@/lib/geo";
import { allStopsQueryOptions } from "@/lib/queries";
import { useTelegram } from "@/lib/telegram";
import { useTheme } from "@/lib/theme";
import { mapCustomizationFor } from "@/lib/yandex-map-styles";
import {
  mapRefererHelp,
  mapRefererShort,
  refererHostnames,
} from "@/lib/yandex-map-theme-legacy";
import { ymaps3LoadDiagnostics } from "@/lib/ymaps3-script-url";
import { resetYmaps3Loader, useYmaps3React } from "@/lib/ymaps3";

const StopMapLegacy = lazy(() =>
  import("@/components/stop-map-legacy").then((m) => ({ default: m.StopMapLegacy })),
);

const MAP_KEY = (import.meta.env.VITE_YANDEX_MAPS_KEY as string | undefined)?.trim() || undefined;

type MapCamera = {
  center: [number, number];
  zoom: number;
  duration?: number;
  easing?: string;
};

const DEFAULT_CAMERA: MapCamera = {
  center: YAROSLAVL_CENTER_LNG_LAT,
  zoom: STOP_MAP_DEFAULT_ZOOM,
};

function MapErrorBoundary({
  onFallback,
  children,
}: {
  onFallback: () => void;
  children: ReactNode;
}) {
  return (
    <MapErrorBoundaryInner onFallback={onFallback}>{children}</MapErrorBoundaryInner>
  );
}

class MapErrorBoundaryInner extends Component<
  { onFallback: () => void; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error) {
    console.error("[Yaride map]", error);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="absolute inset-0 grid place-items-center bg-secondary px-6 text-center">
          <p className="text-sm text-muted-foreground mb-4">Карта временно недоступна</p>
          <button
            type="button"
            onClick={this.props.onFallback}
            className="h-11 px-5 rounded-xl bg-primary text-primary-foreground font-semibold press"
          >
            Выбрать списком
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function StopMarker({
  selected,
  onSelect,
}: {
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-label="Остановка"
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      className={`yaride-map-marker press ${selected ? "yaride-map-marker--selected" : ""}`}
    />
  );
}

function GeoMarker() {
  return <span className="yaride-map-marker yaride-map-marker--geo" aria-hidden />;
}

function MapV3FallbackNotice({
  error,
  onRetry,
  onDismiss,
}: {
  error: string;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hostname = typeof window !== "undefined" ? window.location.hostname : "";
  const diag = ymaps3LoadDiagnostics();

  return (
    <div className="mb-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-[12px] leading-snug">
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 text-foreground">
          <span className="font-semibold">Упрощённая карта (API 2.1).</span>{" "}
          {mapRefererShort(hostname)}
        </p>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 p-0.5 text-muted-foreground press"
          aria-label="Скрыть подсказку"
        >
          <X className="size-4" />
        </button>
      </div>
      <p className="mt-1 text-muted-foreground">{error}</p>
      <p className="mt-1 text-[11px] text-muted-foreground font-mono break-all">
        host: {diag.hostname || "—"} · referrer: {diag.referrer}
        {diag.viaProxy ? " · proxy" : ""}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="inline-flex items-center gap-1 font-semibold text-link press"
        >
          {expanded ? "Свернуть" : "Подробнее"}
          {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </button>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center rounded-lg bg-card border border-border px-2.5 py-1 font-semibold text-foreground press"
        >
          Повторить
        </button>
      </div>
      {expanded ? (
        <div className="mt-2 rounded-lg bg-card/80 border border-border px-2.5 py-2 text-muted-foreground whitespace-pre-line">
          {mapRefererHelp(hostname)}
          <div className="mt-2 font-mono text-[11px] text-foreground">
            {refererHostnames(hostname).join("\n")}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function StopMapPicker({
  title,
  subtitle,
  onConfirm,
  onListFallback,
}: {
  title: string;
  subtitle?: string;
  onConfirm: (stop: ApiMapStop) => void;
  onListFallback?: () => void;
}) {
  const { haptic } = useTelegram();
  const { resolved: theme } = useTheme();
  const [v3RetryKey, setV3RetryKey] = useState(0);
  const [fallbackNoticeDismissed, setFallbackNoticeDismissed] = useState(false);
  const { api: ymaps, loading: mapLoading, error: mapError } = useYmaps3React(MAP_KEY, v3RetryKey);
  const stopsQ = useQuery(allStopsQueryOptions());
  const stops = stopsQ.data?.stops ?? [];
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mapCamera, setMapCamera] = useState<MapCamera>(DEFAULT_CAMERA);
  const [query, setQuery] = useState("");
  const [geoPoint, setGeoPoint] = useState<[number, number] | null>(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return stops.slice(0, 8);
    return stops.filter((s) => s.title.toLowerCase().includes(q)).slice(0, 12);
  }, [query, stops]);

  const selected = stops.find((s) => s.id === selectedId) ?? null;
  const customization = mapCustomizationFor(theme);

  const focusStop = (stop: ApiMapStop) => {
    setMapCamera({
      center: [stop.lng, stop.lat],
      zoom: STOP_MAP_FOCUS_ZOOM,
      duration: 480,
      easing: "ease-in-out",
    });
  };

  const selectStop = (id: number) => {
    haptic("selection");
    setSelectedId(id);
    const stop = stops.find((s) => s.id === id);
    if (stop) focusStop(stop);
  };

  const locateMe = () => {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError("Геолокация недоступна");
      return;
    }
    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setGeoPoint([lat, lng]);
        const nearest = findNearestStop(stops, lat, lng);
        if (nearest) {
          setSelectedId(nearest.id);
          focusStop(nearest);
          haptic("success");
        } else {
          setGeoError("Рядом нет остановок из каталога");
        }
        setGeoLoading(false);
      },
      () => {
        setGeoLoading(false);
        setGeoError("Не удалось получить геолокацию");
      },
      { enableHighAccuracy: true, timeout: 12_000 },
    );
  };

  if (!MAP_KEY) {
    return (
      <div className="min-h-dvh bg-background text-foreground px-5 pt-5">
        <ScreenHeader title={title} subtitle="Карта временно недоступна" />
        <p className="text-sm text-muted-foreground">
          {import.meta.env.DEV ? (
            <>
              Добавьте <code className="text-foreground">VITE_YANDEX_MAPS_KEY</code> в{" "}
              <code className="text-foreground">miniapp/.env</code> или{" "}
              <code className="text-foreground">YANDEX_GEOCODER_KEY</code> в корневой{" "}
              <code className="text-foreground">.env</code>, затем перезапустите{" "}
              <code className="text-foreground">npm run dev</code>.
            </>
          ) : (
            <>Выберите остановку из списка районов — так же быстро и точно по каталогу Yaride.</>
          )}
        </p>
        {onListFallback ? (
          <button
            type="button"
            onClick={onListFallback}
            className="mt-6 h-12 w-full px-5 rounded-xl bg-primary text-primary-foreground font-semibold press"
          >
            Выбрать списком
          </button>
        ) : null}
      </div>
    );
  }

  const { YMap, YMapDefaultSchemeLayer, YMapDefaultFeaturesLayer, YMapMarker } = ymaps ?? {};

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <div className="shrink-0 px-4 pt-4 pb-2 bg-background/95 backdrop-blur border-b border-border safe-top">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-[22px] font-extrabold leading-tight">{title}</h1>
            {subtitle ? <p className="text-[13px] text-muted-foreground mt-1">{subtitle}</p> : null}
          </div>
          {onListFallback ? (
            <button
              type="button"
              onClick={onListFallback}
              className="shrink-0 text-[13px] font-semibold text-link px-2 py-1"
            >
              Списком
            </button>
          ) : null}
        </div>
        <div className="mt-3 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <TextInput
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск остановки"
            className="!pl-10 !h-11"
          />
        </div>
        {query.trim() && filtered.length > 0 ? (
          <div className="mt-2 max-h-36 overflow-y-auto rounded-xl border border-border bg-card divide-y divide-border">
            {filtered.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  selectStop(s.id);
                  setQuery("");
                }}
                className="w-full text-left px-3 py-2.5 text-[14px] press"
              >
                <div className="font-medium">{s.title}</div>
                <div className="text-[12px] text-muted-foreground">{s.district ?? "Ярославль"}</div>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="relative flex-1 min-h-0 bg-background">
        <MapErrorBoundary onFallback={() => (onListFallback ? onListFallback() : undefined)}>
          {stopsQ.isLoading || mapLoading ? (
            <div className="absolute inset-0 grid place-items-center bg-secondary animate-pulse" />
          ) : mapError ? (
            <Suspense
              fallback={<div className="absolute inset-0 grid place-items-center bg-secondary animate-pulse" />}
            >
              <StopMapLegacy
                mapKey={MAP_KEY}
                theme={theme}
                stops={stops}
                selectedId={selectedId}
                geoPoint={geoPoint}
                onSelect={selectStop}
              />
            </Suspense>
          ) : YMap && YMapDefaultSchemeLayer && YMapDefaultFeaturesLayer && YMapMarker ? (
            <YMap
              location={mapCamera}
              mode="vector"
              zoomRange={STOP_MAP_ZOOM_RANGE}
              style={{ width: "100%", height: "100%" }}
            >
              <YMapDefaultSchemeLayer key={theme} theme={theme} customization={customization} />
              <YMapDefaultFeaturesLayer />
              {stops.map((s) => (
                <YMapMarker key={s.id} coordinates={[s.lng, s.lat]} zIndex={s.id === selectedId ? 2 : 1}>
                  <StopMarker
                    selected={s.id === selectedId}
                    onSelect={() => selectStop(s.id)}
                  />
                </YMapMarker>
              ))}
              {geoPoint ? (
                <YMapMarker coordinates={[geoPoint[1], geoPoint[0]]} zIndex={3}>
                  <GeoMarker />
                </YMapMarker>
              ) : null}
            </YMap>
          ) : null}
        </MapErrorBoundary>

        <button
          type="button"
          onClick={locateMe}
          disabled={geoLoading || stopsQ.isLoading || mapLoading}
          className="absolute right-4 top-4 z-10 size-12 rounded-full bg-card border border-border shadow-elevated grid place-items-center press"
          aria-label="Моё местоположение"
        >
          <Navigation className={`size-5 ${geoLoading ? "animate-pulse" : ""}`} />
        </button>
      </div>

      <div className="shrink-0 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+12px)] bg-background/95 backdrop-blur border-t border-border">
        {mapError && !fallbackNoticeDismissed ? (
          <MapV3FallbackNotice
            error={mapError}
            onDismiss={() => setFallbackNoticeDismissed(true)}
            onRetry={() => {
              resetYmaps3Loader();
              setFallbackNoticeDismissed(false);
              setV3RetryKey((k) => k + 1);
            }}
          />
        ) : null}
        {geoError ? <p className="text-xs text-destructive mb-2">{geoError}</p> : null}
        {selected ? (
          <div className="mb-3 flex items-start gap-3">
            <div className="size-10 rounded-full bg-accent text-accent-foreground grid place-items-center shrink-0">
              <MapPin className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="font-semibold text-[15px] leading-tight">{selected.title}</div>
              <div className="text-[12px] text-muted-foreground mt-0.5">
                {selected.district ?? "Ярославль"}
                {selected.adminArea ? ` · ${selected.adminArea}` : ""}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-[13px] text-muted-foreground mb-3">Нажмите на маркер остановки из каталога</p>
        )}
        <Button
          className="w-full"
          disabled={!selected}
          onClick={() => selected && onConfirm(selected)}
        >
          Подтвердить
        </Button>
      </div>
    </div>
  );
}
