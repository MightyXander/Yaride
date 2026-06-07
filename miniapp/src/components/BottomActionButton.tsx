import { Icon } from "./Icon";
import { useMainButton } from "../telegram/hooks";

interface BottomActionButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  withArrow?: boolean;
  loading?: boolean;
}

// Основное действие экрана. Зеркалит нативную Telegram MainButton (через хук),
// а визуально дублируется фиксированной кнопкой внизу — чтобы работало и в браузере.
export function BottomActionButton({
  label,
  onClick,
  disabled = false,
  withArrow = false,
  loading = false,
}: BottomActionButtonProps) {
  useMainButton(label, onClick, { active: !disabled });

  return (
    <div className="fixed bottom-0 left-0 w-full p-margin-page bg-gradient-to-t from-surface via-surface to-transparent pt-10 dark:from-background dark:via-background">
      <button
        onClick={disabled ? undefined : onClick}
        disabled={disabled}
        className={`w-full h-14 font-headline-md rounded-xl active:scale-95 transition-transform flex items-center justify-center gap-2 shadow-lg shadow-primary/20 ${
          disabled
            ? "bg-surface-container-high text-on-surface-variant/60 shadow-none"
            : "bg-primary text-on-primary"
        }`}
      >
        {loading ? (
          <Icon name="progress_activity" className="animate-spin" />
        ) : (
          <>
            <span>{label}</span>
            {withArrow && <Icon name="chevron_right" />}
          </>
        )}
      </button>
    </div>
  );
}
