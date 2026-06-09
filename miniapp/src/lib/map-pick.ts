export type MapPickFlow = "create" | "search";
export type MapPickLeg = "from" | "to";

export interface MapPickPayload {
  flow: MapPickFlow;
  leg: MapPickLeg;
  pointId: number;
  label: string;
  fromPointId?: number;
  fromLabel?: string;
}

/** Search-параметры возврата с экрана карты (надёжнее sessionStorage в Telegram WebView). */
export type MapPickSearch = {
  mpLeg?: MapPickLeg;
  mpId?: number;
  mpLabel?: string;
  mpFromId?: number;
  mpFromLabel?: string;
};

const KEY = "yaride.map.pick.v1";

export function parseOptionalInt(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const n = Number(value);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

export function parseMapPickSearch(search: Record<string, unknown>): MapPickSearch {
  const mpLeg = search.mpLeg === "to" ? "to" : search.mpLeg === "from" ? "from" : undefined;
  return {
    mpLeg,
    mpId: parseOptionalInt(search.mpId),
    mpLabel: typeof search.mpLabel === "string" ? search.mpLabel : undefined,
    mpFromId: parseOptionalInt(search.mpFromId),
    mpFromLabel: typeof search.mpFromLabel === "string" ? search.mpFromLabel : undefined,
  };
}

export function mapPickToSearch(payload: MapPickPayload): MapPickSearch {
  return {
    mpLeg: payload.leg,
    mpId: payload.pointId,
    mpLabel: payload.label,
    ...(payload.fromPointId != null && payload.fromLabel
      ? { mpFromId: payload.fromPointId, mpFromLabel: payload.fromLabel }
      : {}),
  };
}

export function mapPickFromSearch(flow: MapPickFlow, search: MapPickSearch): MapPickPayload | null {
  if (!search.mpLeg || search.mpId == null || !search.mpLabel?.trim()) return null;
  return {
    flow,
    leg: search.mpLeg,
    pointId: search.mpId,
    label: search.mpLabel,
    fromPointId: search.mpFromId,
    fromLabel: search.mpFromLabel,
  };
}

export function saveMapPick(payload: MapPickPayload) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(payload));
  } catch {
    /* ignore */
  }
}

export function consumeMapPick(): MapPickPayload | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const data = JSON.parse(raw) as MapPickPayload;
    if (typeof data?.pointId !== "number" || !data.label?.trim()) return null;
    return data;
  } catch {
    return null;
  }
}

export function readPendingMapPick(flow: MapPickFlow, search: MapPickSearch): MapPickPayload | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) {
      const data = JSON.parse(raw) as MapPickPayload;
      if (data?.flow === flow && typeof data.pointId === "number" && data.label?.trim()) {
        sessionStorage.removeItem(KEY);
        return data;
      }
    }
  } catch {
    /* ignore */
  }
  return mapPickFromSearch(flow, search);
}

export function hasMapPickSearch(search: MapPickSearch): boolean {
  return Boolean(search.mpLeg && search.mpId != null && search.mpLabel);
}
