import type { ReactNode } from "react";

interface ScreenProps {
  children: ReactNode;
  // Отступ сверху под фиксированную шапку (+ полосу прогресса).
  topPad?: "header" | "progress" | "none";
  // Нижний отступ под фиксированную кнопку / нижнюю навигацию.
  bottomPad?: "button" | "nav" | "both" | "none";
  className?: string;
}

const TOP: Record<NonNullable<ScreenProps["topPad"]>, string> = {
  header: "pt-20",
  progress: "pt-24",
  none: "pt-4",
};

const BOTTOM: Record<NonNullable<ScreenProps["bottomPad"]>, string> = {
  button: "pb-32",
  nav: "pb-24",
  both: "pb-44",
  none: "pb-6",
};

// Прокручиваемый контейнер контента с корректными safe-отступами под Telegram-хром.
export function Screen({ children, topPad = "header", bottomPad = "nav", className = "" }: ScreenProps) {
  return (
    <main
      className={`px-margin-page min-h-screen flex flex-col gap-gutter-stack ${TOP[topPad]} ${BOTTOM[bottomPad]} ${className}`}
    >
      {children}
    </main>
  );
}
