import darkCustomization from "@/data/yandex-map-dark.json";
import lightCustomization from "@/data/yandex-map-light.json";
import type { YMapCustomization } from "@/types/ymaps3";

export function mapCustomizationFor(theme: "light" | "dark"): YMapCustomization {
  return (theme === "dark" ? darkCustomization : lightCustomization) as YMapCustomization;
}
