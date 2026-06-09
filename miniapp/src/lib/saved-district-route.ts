export interface SavedDistrictRoute {
  fromDistrict: string;
  toDistrict: string;
  savedAt: number;
}

const STORAGE_KEY = "yaride:saved-district-routes";

export function saveDistrictRoute(fromDistrict: string, toDistrict: string): void {
  const from = fromDistrict.trim();
  const to = toDistrict.trim();
  if (!from || !to) return;
  try {
    const prev = listSavedDistrictRoutes().filter(
      (r) => !(r.fromDistrict === from && r.toDistrict === to),
    );
    const next: SavedDistrictRoute[] = [{ fromDistrict: from, toDistrict: to, savedAt: Date.now() }, ...prev].slice(
      0,
      12,
    );
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* private mode / quota */
  }
}

export function listSavedDistrictRoutes(): SavedDistrictRoute[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedDistrictRoute[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
