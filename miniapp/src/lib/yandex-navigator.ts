export interface LatLng {
  lat: number;
  lng: number;
}

function fmtCoord(value: number): string {
  return value.toFixed(6);
}

function pointSegment({ lat, lng }: LatLng): string {
  return `${fmtCoord(lat)},${fmtCoord(lng)}`;
}

/** HTTPS-маршрут: текущая геолокация → старт → финиш (работает в Telegram через openLink). */
export function buildYandexMapsTripUrl(current: LatLng, start: LatLng, end: LatLng): string {
  const rtext = [pointSegment(current), pointSegment(start), pointSegment(end)].join("~");
  return `https://yandex.ru/maps/?rtext=${encodeURIComponent(rtext)}&rtt=auto`;
}

export function tripHasRouteCoords(trip: {
  startLat?: number | null;
  startLng?: number | null;
  endLat?: number | null;
  endLng?: number | null;
}): trip is { startLat: number; startLng: number; endLat: number; endLng: number } {
  return (
    typeof trip.startLat === "number" &&
    typeof trip.startLng === "number" &&
    typeof trip.endLat === "number" &&
    typeof trip.endLng === "number"
  );
}

export function getCurrentPosition(): Promise<LatLng> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Геолокация недоступна"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => reject(new Error("Не удалось получить геолокацию")),
      { enableHighAccuracy: true, timeout: 12_000 },
    );
  });
}

export async function openTripInYandexNavigator(
  start: LatLng,
  end: LatLng,
  openExternal: (url: string) => void,
): Promise<void> {
  const current = await getCurrentPosition();
  openExternal(buildYandexMapsTripUrl(current, start, end));
}
