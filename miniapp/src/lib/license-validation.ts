export const LICENSE_REGEX = /^\d{2}\s?[А-ЯA-Z]{2}\s?\d{6}$|^\d{4}\s?\d{6}$/i;

export function isLicenseSeriesValid(series: string): boolean {
  return LICENSE_REGEX.test(series.trim());
}

export function isLicenseExpiresValid(expires: string): boolean {
  if (!expires) return false;
  const d = new Date(expires);
  return !Number.isNaN(d.getTime()) && d.getTime() > Date.now();
}
