import { useLocation, useNavigate } from "react-router-dom";
import { Icon } from "./Icon";

interface NavItem {
  icon: string;
  label: string;
  path: string;
}

const ITEMS: NavItem[] = [
  { icon: "search", label: "Поиск", path: "/search" },
  { icon: "directions_car", label: "Поездки", path: "/" },
  { icon: "person", label: "Профиль", path: "/account" },
];

// Нижняя навигация Telegram-стиля: Поиск / Поездки / Профиль.
export function BottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 w-full z-40 flex justify-around items-center px-2 py-2 bg-surface dark:bg-background border-t border-outline-variant/20 h-16">
      {ITEMS.map((item) => {
        const active = pathname === item.path;
        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`flex flex-col items-center justify-center active:scale-95 transition-transform duration-150 ${
              active
                ? "text-primary dark:text-inverse-primary font-bold"
                : "text-on-surface-variant dark:text-outline"
            }`}
          >
            <Icon name={item.icon} filled={active} />
            <span className="font-label-sm text-label-sm">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
