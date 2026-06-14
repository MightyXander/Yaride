/** Проверка серии/номера ВУ РФ — зеркало app/driver_license.py (4 цифры + 2 буквы + 6 цифр). */

const DL_LETTERS = new Set("АВЕКМНОРСТУХ".split(""));

const LATIN_TO_RU: Record<string, string> = {
  A: "А",
  B: "В",
  E: "Е",
  K: "К",
  M: "М",
  H: "Н",
  O: "О",
  P: "Р",
  C: "С",
  T: "Т",
  Y: "У",
  X: "Х",
};

/** Нормализует в 12 символов без разделителей или null при ошибке. */
export function normalizeLicenseSeries(raw: string): string | null {
  if (!raw?.trim()) return null;

  const compact: string[] = [];
  for (const ch of raw.trim()) {
    if (/\s/.test(ch) || ch === "-" || ch === "–" || ch === "—") continue;
    if (/\d/.test(ch)) {
      compact.push(ch);
      continue;
    }
    if (/[a-zA-Zа-яА-ЯёЁ]/.test(ch)) {
      const upper = ch.toUpperCase();
      const ru = DL_LETTERS.has(upper) ? upper : LATIN_TO_RU[upper];
      if (!ru || !DL_LETTERS.has(ru)) return null;
      compact.push(ru);
      continue;
    }
    return null;
  }

  const s = compact.join("");
  if (s.length !== 12) return null;
  if (!/^\d{4}/.test(s)) return null;
  if (!DL_LETTERS.has(s[4]!) || !DL_LETTERS.has(s[5]!)) return null;
  if (!/^\d{6}$/.test(s.slice(6))) return null;
  return s;
}

export function isLicenseSeriesValid(series: string): boolean {
  return normalizeLicenseSeries(series) !== null;
}

export function isLicenseExpiresValid(expires: string): boolean {
  if (!expires) return false;
  const d = new Date(expires);
  return !Number.isNaN(d.getTime()) && d.getTime() > Date.now();
}
