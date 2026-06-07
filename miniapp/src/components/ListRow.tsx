import { Icon } from "./Icon";

interface ListRowProps {
  title: string;
  subtitle?: string;
  icon?: string;
  iconBg?: string;
  trailing?: string;
  onClick?: () => void;
}

// Строка-кнопка списка (выбор района/остановки): иконка-плашка + текст + шеврон.
export function ListRow({ title, subtitle, icon, iconBg, trailing, onClick }: ListRowProps) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-4 bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-3 active:scale-[0.98] transition-transform text-left"
    >
      {icon && (
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${iconBg ?? "bg-surface-container"}`}>
          <Icon name={icon} />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="font-body-lg text-body-lg text-on-surface truncate">{title}</p>
        {subtitle && <p className="font-label-md text-label-md text-on-surface-variant truncate">{subtitle}</p>}
      </div>
      {trailing && <span className="font-label-md text-label-md text-primary">{trailing}</span>}
      <Icon name="chevron_right" className="text-outline-variant shrink-0" />
    </button>
  );
}
