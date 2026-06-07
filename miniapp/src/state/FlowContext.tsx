import { createContext, useContext, useState, type ReactNode } from "react";

export type FlowMode = "search" | "create";

// Состояние конструктора маршрута/поездки, общее для экранов района→остановки→даты→...
export interface FlowState {
  mode: FlowMode;
  startPointId: number | null;
  startLabel: string | null;
  endPointId: number | null;
  endLabel: string | null;
  tripDate: string | null; // YYYY-MM-DD
  departureTime: string | null; // HH:MM
  seats: number;
  priceRub: number;
  comment: string;
  // Публикация из шаблона: id выбранного маршрута-шаблона.
  templateId: number | null;
}

const EMPTY: FlowState = {
  mode: "search",
  startPointId: null,
  startLabel: null,
  endPointId: null,
  endLabel: null,
  tripDate: null,
  departureTime: null,
  seats: 4,
  priceRub: 150,
  comment: "",
  templateId: null,
};

interface FlowContextValue {
  flow: FlowState;
  patch: (p: Partial<FlowState>) => void;
  reset: (mode: FlowMode) => void;
}

const FlowContext = createContext<FlowContextValue | null>(null);

export function FlowProvider({ children }: { children: ReactNode }) {
  const [flow, setFlow] = useState<FlowState>(EMPTY);
  const patch = (p: Partial<FlowState>) => setFlow((prev) => ({ ...prev, ...p }));
  const reset = (mode: FlowMode) => setFlow({ ...EMPTY, mode });
  return <FlowContext.Provider value={{ flow, patch, reset }}>{children}</FlowContext.Provider>;
}

export function useFlow(): FlowContextValue {
  const ctx = useContext(FlowContext);
  if (!ctx) throw new Error("useFlow must be used within FlowProvider");
  return ctx;
}
