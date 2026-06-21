export type SearchPhaseKind =
  | "from-district"
  | "from-stop"
  | "from-geo"
  | "to-district"
  | "to-stop"
  | "date"
  | "results";

export interface SearchWizardDraft {
  phaseKind: SearchPhaseKind;
  fromPointId: number | null;
  fromLabel: string;
  toPointId: number | null;
  toLabel: string;
  fromDistrict: string;
  toDistrict: string;
  pickDistrict: string;
  date: string;
  resultsMode: "exact" | "district";
  departureTimeFilter: string | null;
  minSeatsFreeFilter: number | null;
}

const KEY = "yaride.search.wizard.v1";

export function defaultSearchWizardDraft(): SearchWizardDraft {
  return {
    phaseKind: "from-district",
    fromPointId: null,
    fromLabel: "",
    toPointId: null,
    toLabel: "",
    fromDistrict: "",
    toDistrict: "",
    pickDistrict: "",
    date: "",
    resultsMode: "exact",
    departureTimeFilter: null,
    minSeatsFreeFilter: null,
  };
}

export function loadSearchWizardDraft(): SearchWizardDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as SearchWizardDraft;
    if (!data || typeof data !== "object") return null;
    return { ...defaultSearchWizardDraft(), ...data };
  } catch {
    return null;
  }
}

export function saveSearchWizardDraft(draft: SearchWizardDraft) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    /* ignore */
  }
}

export function clearSearchWizardDraft() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
