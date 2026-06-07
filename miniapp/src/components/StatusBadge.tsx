export type BookingStatus = "active" | "cancelled" | "draft" | "completed";

const STYLES: Record<BookingStatus, { bg: string; text: string; label: string }> = {
  active: { bg: "bg-secondary/10", text: "text-secondary", label: "Активна" },
  completed: { bg: "bg-secondary/10", text: "text-secondary", label: "Завершена" },
  cancelled: { bg: "bg-error/10", text: "text-error", label: "Отменена" },
  draft: { bg: "bg-surface-container-high", text: "text-on-surface-variant", label: "Черновик" },
};

interface StatusBadgeProps {
  status: BookingStatus;
  label?: string;
}

// Пилюля-статус: Активна (зелёная) / Отменена (красная) / Черновик (серая).
export function StatusBadge({ status, label }: StatusBadgeProps) {
  const s = STYLES[status];
  return (
    <span className={`${s.bg} px-3 py-1 rounded-full text-label-sm font-label-sm ${s.text}`}>
      {label ?? s.label}
    </span>
  );
}
