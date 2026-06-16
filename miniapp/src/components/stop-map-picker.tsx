import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { MapPin, Navigation, Search } from "lucide-react";
import L from "leaflet";
import { Button, ScreenHeader, TextInput } from "@/components/ui-kit";
import type { ApiMapStop } from "@/lib/api";
import { findNearestStop, STOP_MAP_FOCUS_ZOOM, YAROSLAVL_CENTER } from "@/lib/geo";
import { allStopsQueryOptions } from "@/lib/queries";
import { useTelegram } from "@/lib/telegram";
import { useTheme } from "@/lib/theme";

// ---------------------------------------------------------------------------
// Tile URLs (CartoDB, без ключа)
// ---------------------------------------------------------------------------
const TILE_DARK = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const TILE_LIGHT = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>';

const MARKER_ZOOM_MIN = 13; // ниже этого зума маркеры скрыты
const DEFAULT_ZOOM = 13;

// ---------------------------------------------------------------------------
// Leaflet иконки
// ---------------------------------------------------------------------------
function makeIcon(selected: boolean) {
  return L.divIcon({
    className: `yaride-map-marker${selected ? " yaride-map-marker--selected" : ""}`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

const GEO_ICON = L.divIcon({
  className: "yaride-map-marker yaride-map-marker--geo",
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

// ---------------------------------------------------------------------------
// Вспомогательные компоненты
// ---------------------------------------------------------------------------
function ZoomWatcher({ onChange }: { onChange: (z: number) => void }) {
  useMapEvents({ zoomend: (e) => onChange(e.target.getZoom()) });
  return null;
}

function FlyTo({ coords, zoom }: { coords: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(coords, zoom, { duration: 0.5 });
  }, [map, coords, zoom]);
  return null;
}

// ---------------------------------------------------------------------------
// Основной компонент
// ---------------------------------------------------------------------------
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
  const stopsQ = useQuery(allStopsQueryOptions());
  const stops = stopsQ.data?.stops ?? [];

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ coords: [number, number]; zoom: number } | null>(null);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [query, setQuery] = useState("");
  const [geoPoint, setGeoPoint] = useState<[number, number] | null>(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const flyKeyRef = useRef(0);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return stops.slice(0, 8);
    return stops.filter((s) => s.title.toLowerCase().includes(q)).slice(0, 12);
  }, [query, stops]);

  const selected = stops.find((s) => s.id === selectedId) ?? null;
  const tileUrl = theme === "dark" ? TILE_DARK : TILE_LIGHT;
  const showMarkers = zoom >= MARKER_ZOOM_MIN;

  const focusStop = (stop: ApiMapStop) => {
    flyKeyRef.current += 1;
    setFlyTarget({ coords: [stop.lat, stop.lng], zoom: STOP_MAP_FOCUS_ZOOM });
  };

  const selectStop = (id: number) => {
    haptic("selection");
    setSelectedId(id);
    const stop = stops.find((s) => s.id === id);
    if (stop) focusStop(stop);
  };

  const locateMe = () => {
    setGeoError(null);
    if (!navigator.geolocation) { setGeoError("Геолокация недоступна"); return; }
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
      () => { setGeoLoading(false); setGeoError("Не удалось получить геолокацию"); },
      { enableHighAccuracy: true, timeout: 12_000 },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      {/* Шапка */}
      <div className="shrink-0 px-4 pt-4 pb-2 bg-background/95 backdrop-blur border-b border-border safe-top">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-[22px] font-extrabold leading-tight">{title}</h1>
            {subtitle ? <p className="text-[13px] text-muted-foreground mt-1">{subtitle}</p> : null}
          </div>
          {onListFallback ? (
            <button type="button" onClick={onListFallback} className="shrink-0 text-[13px] font-semibold text-link px-2 py-1">
              Списком
            </button>
          ) : null}
        </div>
        <div className="mt-3 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <TextInput value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Поиск остановки" className="!pl-10 !h-11" />
        </div>
        {query.trim() && filtered.length > 0 ? (
          <div className="mt-2 max-h-36 overflow-y-auto rounded-xl border border-border bg-card divide-y divide-border">
            {filtered.map((s) => (
              <button key={s.id} type="button" onClick={() => { selectStop(s.id); setQuery(""); }} className="w-full text-left px-3 py-2.5 text-[14px] press">
                <div className="font-medium">{s.title}</div>
                <div className="text-[12px] text-muted-foreground">{s.district ?? "Ярославль"}</div>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {/* Карта */}
      <div className="relative flex-1 min-h-0">
        {stopsQ.isLoading ? (
          <div className="absolute inset-0 bg-secondary animate-pulse" />
        ) : (
          <MapContainer
            center={YAROSLAVL_CENTER}
            zoom={DEFAULT_ZOOM}
            zoomControl={false}
            style={{ width: "100%", height: "100%" }}
          >
            <TileLayer key={tileUrl} url={tileUrl} attribution={TILE_ATTR} maxZoom={18} />
            <ZoomWatcher onChange={setZoom} />
            {flyTarget ? <FlyTo key={flyKeyRef.current} coords={flyTarget.coords} zoom={flyTarget.zoom} /> : null}
            {showMarkers && stops.map((s) => (
              <Marker
                key={s.id}
                position={[s.lat, s.lng]}
                icon={makeIcon(s.id === selectedId)}
                zIndexOffset={s.id === selectedId ? 100 : 0}
                eventHandlers={{ click: () => selectStop(s.id) }}
              />
            ))}
            {geoPoint ? <Marker position={geoPoint} icon={GEO_ICON} /> : null}
          </MapContainer>
        )}

        {/* Кнопка геолокации */}
        <button
          type="button"
          onClick={locateMe}
          disabled={geoLoading || stopsQ.isLoading}
          className="absolute right-4 top-4 z-[1000] size-12 rounded-full bg-card border border-border shadow-elevated grid place-items-center press"
          aria-label="Моё местоположение"
        >
          <Navigation className={`size-5 ${geoLoading ? "animate-pulse" : ""}`} />
        </button>
      </div>

      {/* Подвал */}
      <div className="shrink-0 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+12px)] bg-background/95 backdrop-blur border-t border-border">
        {geoError ? <p className="text-xs text-destructive mb-2">{geoError}</p> : null}
        {selected ? (
          <div className="mb-3 flex items-start gap-3">
            <div className="size-10 rounded-full bg-accent text-accent-foreground grid place-items-center shrink-0">
              <MapPin className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="font-semibold text-[15px] leading-tight">{selected.title}</div>
              <div className="text-[12px] text-muted-foreground mt-0.5">
                {selected.district ?? "Ярославль"}{selected.adminArea ? ` · ${selected.adminArea}` : ""}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-[13px] text-muted-foreground mb-3">Нажмите на маркер остановки из каталога</p>
        )}
        <Button className="w-full" disabled={!selected} onClick={() => selected && onConfirm(selected)}>
          Подтвердить
        </Button>
      </div>
    </div>
  );
}
