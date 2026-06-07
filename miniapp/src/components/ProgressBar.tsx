interface ProgressBarProps {
  step: number;
  total: number;
}

// Тонкая фиксированная полоса прогресса сразу под шапкой.
// Подпись «Шаг N из M» экраны выводят сами в потоке контента.
export function ProgressBar({ step, total }: ProgressBarProps) {
  const pct = Math.min(100, Math.round((step / total) * 100));
  return (
    <div className="fixed top-14 left-0 h-0.5 w-full bg-surface-container-highest z-[60]">
      <div className="h-full bg-primary transition-all duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}

// Подпись шага для размещения в начале контента.
export function StepCaption({ step, total }: ProgressBarProps) {
  return (
    <p className="text-center text-label-sm font-label-sm text-on-surface-variant uppercase tracking-wider">
      Шаг {step} из {total}
    </p>
  );
}
