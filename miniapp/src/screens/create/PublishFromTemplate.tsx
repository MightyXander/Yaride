import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { Calendar } from "../../components/Calendar";
import { Chip } from "../../components/Chip";
import { BottomActionButton } from "../../components/BottomActionButton";
import { api, ApiError } from "../../api/client";
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

// Быстрая публикация поездки из шаблона: маршрут/цена/места уже заданы — выбираем только дату и время.
export function PublishFromTemplate() {
  const navigate = useNavigate();
  const { flow } = useFlow();
  const today = new Date();
  const [date, setDate] = useState<Date | null>(today);
  const [time, setTime] = useState<string | null>(() => defaultTimeFor(today));
  const [published, setPublished] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isToday = date && date.toDateString() === today.toDateString();
  const isTomorrow = date && date.toDateString() === addDays(today, 1).toDateString();

  const selectDate = (d: Date) => {
    setDate(d);
    setTime(defaultTimeFor(d));
  };

  const publish = async () => {
    if (!flow.templateId || !date || !time || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.publishTemplate(flow.templateId, { trip_date: toIso(date), departure_time: time });
      setPublished(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось опубликовать поездку");
      setSubmitting(false);
    }
  };

  return (
    <>
      <Header title="Публикация" centerTitle onBack={() => navigate(-1)} />

      <main className="pt-20 pb-32 px-margin-page min-h-screen flex flex-col gap-6">
        <div className="bg-surface-container-low rounded-xl p-padding-card border border-outline-variant/20">
          <p className="font-headline-md text-headline-md-mobile text-on-surface">
            {flow.startLabel} <Icon name="arrow_forward" className="text-[16px] text-outline align-middle" /> {flow.endLabel}
          </p>
          <p className="font-label-md text-label-md text-on-surface-variant mt-1">
            {flow.priceRub} ₽ · {flow.seats} мест
          </p>
        </div>

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

        {error && <p className="text-center text-label-md font-label-md text-error">{error}</p>}
      </main>

      <BottomActionButton
        label={submitting ? "Публикуем…" : "Опубликовать"}
        onClick={publish}
        disabled={!date || !time || submitting}
        loading={submitting}
      />

      {published && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100] flex items-center justify-center p-6">
          <div className="bg-surface-container-lowest rounded-xl p-8 w-full max-w-xs flex flex-col items-center text-center">
            <div className="w-16 h-16 bg-secondary-container text-on-secondary-container rounded-full flex items-center justify-center mb-6">
              <Icon name="check_circle" filled className="text-[40px]" />
            </div>
            <h2 className="font-headline-lg text-headline-lg mb-2 text-on-surface">Готово!</h2>
            <p className="font-body-md text-body-md text-on-surface-variant mb-6">Поездка опубликована.</p>
            <button
              onClick={() => navigate("/")}
              className="w-full h-12 bg-secondary text-on-secondary rounded-lg font-label-md text-label-md"
            >
              На главную
            </button>
          </div>
        </div>
      )}
    </>
  );
}
