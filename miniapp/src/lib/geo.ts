import type { ApiMapStop } from "./api";

const EARTH_RADIUS_KM = 6371;

export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
}

export function findNearestStop(stops: ApiMapStop[], lat: number, lng: number): ApiMapStop | null {
  if (stops.length === 0) return null;
  let best: ApiMapStop | null = null;
  let bestKm = Infinity;
  for (const s of stops) {
    const km = haversineKm(lat, lng, s.lat, s.lng);
    if (km < bestKm) {
      bestKm = km;
      best = s;
    }
  }
  return best;
}

/** Центр Ярославля для карты (API 2.1: lat, lng). */
export const YAROSLAVL_CENTER: [number, number] = [57.6261, 39.8845];

/** Центр Ярославля для Yandex Maps API 3 (lng, lat). */
export const YAROSLAVL_CENTER_LNG_LAT: [number, number] = [39.8845, 57.6261];

/** Обзор города при открытии карты выбора остановки. */
export const STOP_MAP_DEFAULT_ZOOM = 12;

/** Авто-приближение при выборе остановки — верхняя граница зума для пользователя. */
export const STOP_MAP_FOCUS_ZOOM = 15;

export const STOP_MAP_ZOOM_RANGE = {
  min: 10,
  max: STOP_MAP_FOCUS_ZOOM,
} as const;
