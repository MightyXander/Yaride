interface ChipProps {
  label: string;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

// Чип выбора (время, места, цена, быстрые даты).
// Выбран — primary-фон с белым текстом; иначе — контейнерный фон.
export function Chip({ label, selected = false, onClick, className = "" }: ChipProps) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-3 rounded-lg font-body-md text-body-md transition-all active:scale-95 ${
        selected
          ? "bg-primary text-on-primary font-semibold"
          : "bg-surface-container text-on-surface"
      } ${className}`}
    >
      {label}
    </button>
  );
}
