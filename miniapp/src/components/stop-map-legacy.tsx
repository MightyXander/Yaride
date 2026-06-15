import { useRef, useEffect } from "react";
import { YMaps, Map, Clusterer, Placemark } from "@pbe/react-yandex-maps";
import type ymaps from "yandex-maps";
import type { ApiMapStop } from "@/lib/api";
import {
  STOP_MAP_DEFAULT_ZOOM,
  STOP_MAP_FOCUS_ZOOM,
  STOP_MAP_ZOOM_RANGE,
  YAROSLAVL_CENTER,
} from "@/lib/geo";
import type { ResolvedTheme } from "@/lib/yandex-maps-diagnostics";

const clusterOptions = {
  preset: "islands#invertedYellowClusterIcons",
  groupByCoordinates: false,
};

type MapWithContainer = ymaps.Map & {
  container?: { getElement?: () => HTMLElement };
};

const DARK_TILE_FILTER =
  "invert(1) hue-rotate(180deg) brightness(0.9) saturate(0.82) contrast(0.94)";

function applyLegacyMapTheme(map: ymaps.Map | undefined, theme: ResolvedTheme) {
  if (!map) return;
  const root = (map as MapWithContainer).container?.getElement?.();
  if (!root) return;
  const filter = theme === "dark" ? DARK_TILE_FILTER : "";
  root.querySelectorAll<HTMLElement>('[class*="layers-pane"], [class*="ground-pane"]').forEach((pane) => {
    pane.style.filter = filter;
  });
}

export function StopMapLegacy({
  mapKey,
  theme,
  stops,
  selectedId,
  geoPoint,
  onSelect,
}: {
  mapKey: string;
  theme: ResolvedTheme;
  stops: ApiMapStop[];
  selectedId: number | null;
  geoPoint: [number, number] | null;
  onSelect: (id: number) => void;
}) {
  const mapRef = useRef<ymaps.Map | undefined>(undefined);

  useEffect(() => {
    applyLegacyMapTheme(mapRef.current, theme);
  }, [theme]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || selectedId == null) return;
    const stop = stops.find((s) => s.id === selectedId);
    if (!stop) return;
    map.setCenter([stop.lat, stop.lng], STOP_MAP_FOCUS_ZOOM, {
      duration: 450,
      timingFunction: "ease-in-out",
    });
  }, [selectedId, stops]);

  return (
    <YMaps query={{ apikey: mapKey, lang: "ru_RU" }}>
      <Map
        defaultState={{ center: YAROSLAVL_CENTER, zoom: STOP_MAP_DEFAULT_ZOOM }}
        width="100%"
        height="100%"
        options={{
          suppressMapOpenBlock: true,
          minZoom: STOP_MAP_ZOOM_RANGE.min,
          maxZoom: STOP_MAP_ZOOM_RANGE.max,
        }}
        instanceRef={(map) => {
          mapRef.current = map ?? undefined;
          if (map) applyLegacyMapTheme(map, theme);
        }}
      >
        <Clusterer options={clusterOptions}>
          {stops.map((s) => (
            <Placemark
              key={s.id}
              geometry={[s.lat, s.lng]}
              options={{ preset: s.id === selectedId ? "islands#yellowIcon" : "islands#yellowDotIcon" }}
              properties={{ hintContent: s.title }}
              onClick={() => onSelect(s.id)}
            />
          ))}
        </Clusterer>
        {geoPoint ? (
          <Placemark geometry={geoPoint} options={{ preset: "islands#blueCircleDotIcon" }} />
        ) : null}
      </Map>
    </YMaps>
  );
}