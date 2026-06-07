import { Icon } from "./Icon";

// Полноэкранный индикатор загрузки.
export function LoadingView({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-on-surface-variant">
      <Icon name="progress_activity" className="animate-spin text-primary text-4xl" />
      <p className="font-body-md text-body-md">{label}</p>
    </div>
  );
}

// Экран ошибки с кнопкой повтора.
export function ErrorView({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-margin-page text-center">
      <div className="w-20 h-20 bg-error-container rounded-full flex items-center justify-center">
        <Icon name="error" filled className="text-error text-4xl" />
      </div>
      <p className="font-body-md text-body-md text-on-surface-variant max-w-[280px]">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="h-11 px-6 rounded-lg bg-primary text-on-primary font-label-md text-label-md active:scale-95 transition-transform"
        >
          Повторить
        </button>
      )}
    </div>
  );
}

// Пустое состояние списка.
export function EmptyView({ icon = "inbox", title, subtitle }: { icon?: string; title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-32 h-32 bg-surface-container rounded-full flex items-center justify-center mb-6">
        <Icon name={icon} className="text-outline text-6xl" />
      </div>
      <h2 className="font-headline-md text-headline-md text-on-surface mb-2">{title}</h2>
      {subtitle && <p className="font-body-md text-body-md text-on-surface-variant max-w-[240px]">{subtitle}</p>}
    </div>
  );
}
