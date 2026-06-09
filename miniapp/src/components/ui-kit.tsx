import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ChevronRight, Star } from "lucide-react";
import type { TripCardData } from "@/lib/adapters";
import { BOTTOM_CTA_ABOVE_FLOATING_NAV } from "@/components/floating-nav";
import { useHideMainButton, useTelegram } from "@/lib/telegram";

export function Screen({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`min-h-dvh bg-background text-foreground pb-32 ${className}`}>
      <div className="stagger-in">{children}</div>
    </div>
  );
}

export function ScreenHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header className="px-5 pt-5 pb-3 flex items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[28px] font-extrabold leading-[1.05] tracking-tight">{title}</h1>
        {subtitle ? <p className="text-[13px] text-muted-foreground mt-1.5">{subtitle}</p> : null}
      </div>
      {right}
    </header>
  );
}

export function Section({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="px-5 mt-4">
      {title ? (
        <h2 className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground px-1 mb-2.5">
          {title}
        </h2>
      ) : null}
      {children}
    </section>
  );
}

export function Card({
  children,
  onClick,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  const Cmp = onClick ? "button" : "div";
  return (
    <Cmp
      onClick={onClick}
      className={`surface-elevated text-elevated-foreground block w-full text-left p-4 ${
        onClick ? "press" : ""
      } ${className}`}
    >
      {children}
    </Cmp>
  );
}

export function ListRow({
  icon,
  title,
  subtitle,
  trailing,
  onClick,
  destructive = false,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  onClick?: () => void;
  destructive?: boolean;
}) {
  const inner = (
    <div className="flex items-center gap-3 px-4 py-3.5">
      {icon ? (
        <div className="size-9 rounded-full bg-accent text-accent-foreground grid place-items-center shrink-0">
          {icon}
        </div>
      ) : null}
      <div className="flex-1 min-w-0">
        <div
          className={`text-[17px] leading-tight truncate ${
            destructive ? "text-destructive" : "text-foreground"
          }`}
        >
          {title}
        </div>
        {subtitle ? (
          <div className="text-[13px] text-muted-foreground truncate mt-0.5">{subtitle}</div>
        ) : null}
      </div>
      {trailing ?? (onClick ? <ChevronRight className="size-5 text-muted-foreground" /> : null)}
    </div>
  );
  if (onClick) {
    return (
      <button onClick={onClick} className="w-full text-left press active:bg-accent/50">
        {inner}
      </button>
    );
  }
  return inner;
}

export function ListGroup({ children }: { children: ReactNode }) {
  return (
    <div className="tg-section text-card-foreground overflow-hidden divide-y divide-border">{children}</div>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "destructive";
  size?: "md" | "sm";
}) {
  const base =
    "inline-flex items-center justify-center font-bold rounded-2xl press disabled:opacity-40 disabled:pointer-events-none";
  const sizes = { md: "h-13 px-5 text-[16px] min-h-[52px]", sm: "h-10 px-4 text-sm" };
  const variants = {
    primary: "brand-gradient brand-glow text-[#18170f]",
    secondary: "bg-secondary text-secondary-foreground",
    ghost: "bg-transparent text-link",
    destructive: "bg-destructive text-destructive-foreground",
  };
  return <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...rest} />;
}

/** In-page bottom CTA (brand yellow). Set `forceInPage` to show inside Telegram instead of MainButton. */
export function BottomCTA({
  text,
  onClick,
  disabled,
  variant = "primary",
  forceInPage = false,
  aboveFloatingNav,
  visible = true,
}: {
  text: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: "primary" | "destructive";
  forceInPage?: boolean;
  /** Поднять над pill-навигацией. По умолчанию — true при `forceInPage`. */
  aboveFloatingNav?: boolean;
  /** Скрыть полностью (не рендерить футер). */
  visible?: boolean;
}) {
  const { isTelegram } = useTelegram();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useHideMainButton(forceInPage && isTelegram && visible);
  if (!visible) return null;
  if (isTelegram && !forceInPage) return null;

  const liftAboveNav = aboveFloatingNav ?? forceInPage;
  const bottom = liftAboveNav
    ? BOTTOM_CTA_ABOVE_FLOATING_NAV
    : "max(12px, env(safe-area-inset-bottom, 0px))";

  const bar = (
    <div
      className={`fixed inset-x-0 z-50 px-4 pt-3 bg-background/95 backdrop-blur ${
        forceInPage ? "" : "border-t border-border"
      } pb-3`}
      style={{ bottom }}
    >
      <Button
        variant={variant}
        disabled={disabled}
        onClick={onClick}
        className="w-full"
      >
        {text}
      </Button>
    </div>
  );

  if (!mounted) return null;
  return createPortal(bar, document.body);
}

export function Chip({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 h-10 rounded-full text-[15px] font-semibold press ${
        active
          ? "brand-gradient text-[#18170f]"
          : "bg-secondary text-secondary-foreground"
      }`}
    >
      {children}
    </button>
  );
}

export function StatusBadge({
  status,
}: {
  status: "active" | "cancelled_by_passenger" | "cancelled_by_driver" | "completed";
}) {
  const map = {
    active: { label: "Активна", bg: "bg-success/15", fg: "text-success" },
    cancelled_by_passenger: {
      label: "Отменена пассажиром",
      bg: "bg-muted",
      fg: "text-muted-foreground",
    },
    cancelled_by_driver: {
      label: "Отменена водителем",
      bg: "bg-destructive/15",
      fg: "text-destructive",
    },
    completed: { label: "Завершена", bg: "bg-accent", fg: "text-accent-foreground" },
  } as const;
  const s = map[status];
  return (
    <span className={`inline-flex items-center px-2.5 h-6 rounded-md text-xs font-medium ${s.bg} ${s.fg}`}>
      {s.label}
    </span>
  );
}

export function RatingStars({
  value,
  onChange,
  size = 24,
}: {
  value: number;
  onChange?: (v: number) => void;
  size?: number;
}) {
  return (
    <div className="flex items-center gap-1.5">
      {[1, 2, 3, 4, 5].map((n) => {
        const filled = n <= Math.round(value);
        return (
          <button
            key={n}
            type="button"
            onClick={() => onChange?.(n)}
            disabled={!onChange}
            className="active:scale-95 transition-transform"
            aria-label={`${n} звёзд`}
          >
            <Star
              size={size}
              className={filled ? "fill-brand text-brand" : "text-muted-foreground"}
              strokeWidth={1.5}
            />
          </button>
        );
      })}
    </div>
  );
}

export function StepperHeader({ step, total, label }: { step: number; total: number; label: string }) {
  return (
    <div className="px-5 pt-4">
      <div className="flex items-center gap-1.5 mb-3">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full ${
              i < step ? "bg-primary" : "bg-secondary"
            }`}
          />
        ))}
      </div>
      <div className="text-xs uppercase tracking-wider text-muted-foreground">
        Шаг {step} из {total} · {label}
      </div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="px-6 py-16 flex flex-col items-center text-center">
      {icon ? (
        <div className="size-16 rounded-full bg-accent text-accent-foreground grid place-items-center mb-4">
          {icon}
        </div>
      ) : null}
      <h3 className="text-lg font-semibold">{title}</h3>
      {description ? (
        <p className="text-sm text-muted-foreground mt-1.5 max-w-xs">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function Field({
  label,
  error,
  children,
  hint,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[13px] font-medium text-muted-foreground mb-1.5 px-1">
        {label}
      </span>
      {children}
      {error ? (
        <span className="block text-xs text-destructive mt-1.5 px-1">{error}</span>
      ) : hint ? (
        <span className="block text-xs text-muted-foreground mt-1.5 px-1">{hint}</span>
      ) : null}
    </label>
  );
}

export function TextInput({
  invalid,
  className = "",
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      {...rest}
      className={`w-full h-12 px-4 rounded-xl bg-input/60 text-foreground placeholder:text-muted-foreground outline-none ring-0 focus:bg-input transition-colors ${
        invalid ? "ring-2 ring-destructive" : ""
      } ${className}`}
    />
  );
}

const WEEKDAYS = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];

export function formatTripDate(iso: string) {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  const wd = WEEKDAYS[d.getDay()];
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${wd.charAt(0).toUpperCase()}${wd.slice(1)} ${dd}.${mm}`;
}

export function TripCard({ trip, onClick }: { trip: TripCardData; onClick?: () => void }) {
  const free = trip.seatsTotal - trip.seatsTaken;
  return (
    <Card onClick={onClick} className="!p-0 overflow-hidden">
      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="size-10 rounded-full brand-gradient grid place-items-center text-[14px] font-extrabold text-[#18170f]">
              {trip.driverName.charAt(0)}
            </div>
            <div className="min-w-0">
              <div className="text-[15px] font-semibold truncate">{trip.driverName}</div>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Star size={12} className="fill-brand text-brand" strokeWidth={0} />
                {(trip.driverRating ?? 0).toFixed(1)}
              </div>
            </div>
          </div>
          <div className="shrink-0 inline-flex items-center gap-1 px-3 h-9 rounded-full brand-gradient text-[#18170f] leading-none">
            <span className="text-[17px] font-extrabold">{trip.price}</span>
            <span className="text-[11px] font-bold opacity-70">₽</span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <div className="mt-1.5 flex flex-col items-center">
            <span className="size-2.5 rounded-full bg-brand" />
            <span className="w-px flex-1 bg-border my-1 min-h-4" />
            <span className="size-2.5 rounded-full border-2 border-brand" />
          </div>
          <div>
            <div className="text-[15px] font-semibold">{trip.fromLabel}</div>
            {trip.fromSub ? <div className="text-xs text-muted-foreground">{trip.fromSub}</div> : null}
            <div className="text-[15px] font-semibold mt-2">{trip.toLabel}</div>
            {trip.toSub ? <div className="text-xs text-muted-foreground">{trip.toSub}</div> : null}
          </div>
        </div>
      </div>

      <div className="hairline-t px-4 py-3 flex items-center justify-between text-[13px] bg-background/40">
        <span className="text-muted-foreground">
          {trip.date ? formatTripDate(trip.date) : "—"} ·{" "}
          <span className="text-foreground font-semibold">{trip.time || "—"}</span>
        </span>
        <span className={`font-semibold ${free === 0 ? "text-destructive" : "text-success"}`}>
          {free === 0 ? "мест нет" : `свободно ${free}/${trip.seatsTotal}`}
        </span>
      </div>
    </Card>
  );
}

export function NavBreadcrumbs({ items }: { items: string[] }) {
  return (
    <nav className="px-5 mt-1 text-xs text-muted-foreground truncate" aria-label="Хлебные крошки">
      {items.map((it, i) => (
        <span key={i}>
          {i > 0 ? <span className="mx-1.5 opacity-60">›</span> : null}
          <span className={i === items.length - 1 ? "text-foreground font-medium" : ""}>{it}</span>
        </span>
      ))}
    </nav>
  );
}
