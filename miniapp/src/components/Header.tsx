import { useNavigate } from "react-router-dom";
import { Icon } from "./Icon";

interface HeaderProps {
  title: string;
  onBack?: () => void;
  showBack?: boolean;
  rightIcon?: string;
  onRight?: () => void;
  centerTitle?: boolean;
}

// Фиксированная верхняя панель: стрелка назад + заголовок + опциональная иконка справа.
// Высота 56px (h-14), бордер снизу — как в Stitch.
export function Header({
  title,
  onBack,
  showBack = true,
  rightIcon,
  onRight,
  centerTitle = false,
}: HeaderProps) {
  const navigate = useNavigate();
  const handleBack = onBack ?? (() => navigate(-1));

  return (
    <header className="fixed top-0 left-0 w-full z-50 flex items-center justify-between px-margin-page h-14 bg-surface dark:bg-background border-b border-outline-variant/20">
      <div className="flex items-center gap-4 min-w-0">
        {showBack && (
          <button
            onClick={handleBack}
            className="active:opacity-70 transition-opacity text-primary dark:text-inverse-primary shrink-0"
            aria-label="Назад"
          >
            <Icon name="arrow_back" />
          </button>
        )}
        <h1
          className={`font-headline-md text-headline-md-mobile font-bold text-primary dark:text-inverse-primary truncate ${
            centerTitle ? "flex-1 text-center" : ""
          }`}
        >
          {title}
        </h1>
      </div>
      {rightIcon ? (
        <button
          onClick={onRight}
          className="text-on-surface-variant active:opacity-70 transition-opacity shrink-0"
        >
          <Icon name={rightIcon} />
        </button>
      ) : (
        centerTitle && <div className="w-6 shrink-0" />
      )}
    </header>
  );
}
