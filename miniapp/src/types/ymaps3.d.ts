export type YMapCustomizationItem = {
  tags?: { all?: string[]; any?: string | string[]; none?: string[] };
  types?: string;
  elements?: string;
  stylers?: Record<string, unknown> | Record<string, unknown>[];
};

export type YMapCustomization = YMapCustomizationItem[];

declare global {
  interface Window {
    ymaps3?: {
      ready: Promise<void>;
      import: (module: string) => Promise<unknown>;
      [key: string]: unknown;
    };
  }
}

export {};
