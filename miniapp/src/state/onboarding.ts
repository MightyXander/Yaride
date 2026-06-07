// Промежуточные данные регистрации между шагами онбординга (name → role → license/car).
// sessionStorage переживает перезагрузку WebView, но очищается при закрытии.

const KEY = "yaride_onboarding";

export interface OnboardingDraft {
  name?: string;
  role?: "driver" | "passenger";
}

export function getDraft(): OnboardingDraft {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

export function patchDraft(p: OnboardingDraft): void {
  sessionStorage.setItem(KEY, JSON.stringify({ ...getDraft(), ...p }));
}

export function clearDraft(): void {
  sessionStorage.removeItem(KEY);
}
