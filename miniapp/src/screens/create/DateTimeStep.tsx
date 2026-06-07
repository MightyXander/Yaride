import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { ProgressBar } from "../../components/ProgressBar";
import { Calendar } from "../../components/Calendar";
import { Chip } from "../../components/Chip";
import { StepCaption } from "../../components/ProgressBar";
import { BottomActionButton } from "../../components/BottomActionButton";
import { timeSlots } from "../../data/mock";
import { useFlow } from "../../state/FlowContext";

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return new Date(r.getFullYear(), r.getMonth(), r.getDate());
}

function toIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function defaultTimeFor(date: Date | null): string | null {
  if (!date) return null;
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (!isToday) return timeSlots[0] ?? null;
  for (const t of timeSlots) {
    const [h, m] = t.split(":").map(Number);
    const slot = new Date(date.getFullYear(), date.getMonth(), date.getDate(), h, m);
    if (slot > now) return t;
  }
  return null;
}

// Создание поездки, шаг даты/времени: быстрые «Сегодня/Завтра» + календарь + слоты времени.
export function DateTimeStep() {
  const navigate = useNavigate();
  const { patch } = useFlow();
  const today = new Date();
  const [date, setDate] = useState<Date | null>(today);
  const [time, setTime] = useState<string | null>(() => defaultTimeFor(today));

  const isToday = date && date.toDateString() === today.toDateString();
  const isTomorrow = date && date.toDateString() === addDays(today, 1).toDateString();

  const selectDate = (d: Date) => {
    setDate(d);
    setTime(defaultTimeFor(d));
  };

  const next = () => {
    if (!date || !time) return;
    patch({ tripDate: toIso(date), departureTime: time });
    navigate("/create/seats-price");
  };

  return (
    <>
      <Header title="Дата и время" centerTitle onBack={() => navigate(-1)} />
      <ProgressBar step={2} total={3} />

      <main className="pt-6 pb-32 px-margin-page min-h-screen flex flex-col gap-6">
        <StepCaption step={2} total={3} />
        <div className="grid grid-cols-2 gap-gap-chip">
          <Chip
            label="Сегодня"
            selected={!!isToday}
            onClick={() => selectDate(today)}
            className={isToday ? "!bg-secondary-fixed !text-on-secondary-fixed-variant" : ""}
          />
          <Chip label="Завтра" selected={!!isTomorrow} onClick={() => selectDate(addDays(today, 1))} />
        </div>

        <Calendar value={date} onChange={(d) => d && selectDate(d)} />

        <div>
          <h3 className="font-headline-md text-headline-md-mobile text-on-surface mb-3">Время отправления</h3>
          <div className="grid grid-cols-4 gap-gap-chip">
            {timeSlots.map((t) => (
              <Chip key={t} label={t} selected={time === t} onClick={() => setTime(t)} />
            ))}
          </div>
        </div>
      </main>

      <BottomActionButton label="Далее" onClick={next} disabled={!date || !time} />
    </>
  );
}
