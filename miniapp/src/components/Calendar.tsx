import { useState } from "react";
import { Icon } from "./Icon";

const MONTHS = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];
const WEEKDAYS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];

interface CalendarProps {
  value: Date | null;
  onChange: (d: Date) => void;
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

// Месячный календарь: прошедшие даты заблокированы (как в YarideCalendar бота).
export function Calendar({ value, onChange }: CalendarProps) {
  const today = startOfDay(new Date());
  const [view, setView] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));

  const year = view.getFullYear();
  const month = view.getMonth();
  const firstDay = new Date(year, month, 1);
  // getDay(): 0=вс..6=сб → приводим к понедельнику первым.
  const leading = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < leading; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));

  const sameDay = (a: Date | null, b: Date | null) =>
    !!a && !!b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  return (
    <div className="bg-surface-container-lowest rounded-xl p-4 border border-outline-variant/20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-headline-md text-headline-md-mobile text-on-surface">
          {MONTHS[month]} {year}
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => setView(new Date(year, month - 1, 1))}
            className="w-8 h-8 flex items-center justify-center rounded-full active:bg-surface-container text-primary"
          >
            <Icon name="chevron_left" />
          </button>
          <button
            onClick={() => setView(new Date(year, month + 1, 1))}
            className="w-8 h-8 flex items-center justify-center rounded-full active:bg-surface-container text-primary"
          >
            <Icon name="chevron_right" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-2">
        {WEEKDAYS.map((w) => (
          <div key={w} className="text-center text-label-sm font-label-sm text-on-surface-variant py-1">
            {w}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((d, i) => {
          if (!d) return <div key={`e${i}`} />;
          const past = d < today;
          const selected = sameDay(d, value);
          return (
            <button
              key={d.toISOString()}
              disabled={past}
              onClick={() => onChange(d)}
              className={`aspect-square flex items-center justify-center rounded-full text-body-md font-body-md transition-colors ${
                selected
                  ? "bg-primary text-on-primary border-2 border-primary"
                  : past
                    ? "text-outline-variant/50"
                    : "text-on-surface active:bg-surface-container"
              }`}
            >
              {d.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
