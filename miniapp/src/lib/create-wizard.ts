export type CreateWizardStep = "start" | "from" | "to" | "date" | "time" | "seats" | "price" | "comment";

export interface CreateWizardDraft {
  step: CreateWizardStep;
  fromPointId: number | null;
  fromLabel: string;
  toPointId: number | null;
  toLabel: string;
  date: string | null;
  time: string | null;
  seats: 2 | 3 | 4;
  price: 100 | 150 | 200;
  comment: string;
}

const KEY = "yaride.create.wizard.v1";

export function defaultCreateWizardDraft(): CreateWizardDraft {
  return {
    step: "start",
    fromPointId: null,
    fromLabel: "",
    toPointId: null,
    toLabel: "",
    date: null,
    time: null,
    seats: 4,
    price: 150,
    comment: "",
  };
}

export function loadCreateWizardDraft(): CreateWizardDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as CreateWizardDraft;
    if (!data || typeof data !== "object") return null;
    return { ...defaultCreateWizardDraft(), ...data };
  } catch {
    return null;
  }
}

export function saveCreateWizardDraft(draft: CreateWizardDraft) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    /* ignore */
  }
}

export function clearCreateWizardDraft() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
