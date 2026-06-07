import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { api, ApiError } from "../../api/client";
import { haptic } from "../../telegram/webapp";

interface CancelState {
  bookingId: number;
  fromTitle: string;
  toTitle: string;
  whenLabel: string;
}

// Отмена брони пассажиром: причина (уйдёт водителю, мин. 3 символа) + предупреждение.
export function CancelBooking() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as CancelState | null;
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = reason.trim().length >= 3;

  const submit = async () => {
    if (!valid || submitting || !state) return;
    haptic("medium");
    setSubmitting(true);
    setError(null);
    try {
      await api.cancelBooking(state.bookingId, reason.trim());
      navigate("/bookings");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось отменить бронь");
      setSubmitting(false);
    }
  };

  return (
    <>
      <Header title="Отмена брони" centerTitle onBack={() => navigate(-1)} />

      <main className="pt-20 pb-28 px-margin-page flex flex-col gap-6">
        <div className="space-y-2">
          <p className="font-body-lg text-body-lg text-on-surface">Напиши причину отмены (она уйдёт водителю)</p>
          <div className="h-1 w-12 bg-primary rounded-full opacity-20" />
        </div>

        <div className="relative">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 500))}
            rows={6}
            placeholder="Например: изменились планы или нашёл другой вариант"
            className="w-full p-padding-card rounded-xl bg-surface-container-low border-none text-on-surface font-body-md text-body-md placeholder:text-outline/50 resize-none focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <div className="absolute bottom-3 right-3 text-label-sm font-label-sm text-outline/40">{reason.length} / 500</div>
        </div>

        <div className="flex gap-4 p-padding-card bg-error-container/30 border border-error/10 rounded-xl items-start">
          <Icon name="warning" filled className="text-error" />
          <div className="flex flex-col gap-1">
            <p className="font-label-md text-label-md text-on-error-container">Внимание</p>
            <p className="font-body-md text-body-md text-on-error-container leading-snug">
              Отмена менее чем за 2 часа может повлиять на ваш рейтинг и доступность будущих поездок.
            </p>
          </div>
        </div>

        {state && (
          <div className="p-padding-card bg-surface-container rounded-xl flex items-center justify-between border border-outline-variant/20">
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Бронирование</span>
              <span className="font-headline-md text-headline-md-mobile text-on-surface">
                {state.fromTitle} → {state.toTitle}
              </span>
              <span className="font-body-md text-body-md text-on-surface-variant">{state.whenLabel}</span>
            </div>
            <div className="h-12 w-12 rounded-full bg-surface-container-highest flex items-center justify-center shrink-0">
              <Icon name="directions_car" className="text-primary" />
            </div>
          </div>
        )}

        {error && <p className="text-center text-label-md font-label-md text-error">{error}</p>}
      </main>

      <div className="fixed bottom-0 left-0 w-full p-margin-page bg-gradient-to-t from-surface via-surface to-transparent pt-10 dark:from-background dark:via-background">
        <button
          onClick={submit}
          disabled={!valid || submitting}
          className={`w-full h-14 rounded-xl font-headline-md-mobile font-bold flex items-center justify-center gap-2 active:scale-95 transition-transform ${
            valid && !submitting ? "bg-error text-on-error shadow-lg shadow-error/20" : "bg-surface-container-high text-on-surface-variant/60"
          }`}
        >
          <Icon name={submitting ? "progress_activity" : "cancel"} className={submitting ? "animate-spin" : ""} />
          {submitting ? "Отменяем…" : "Отменить бронь"}
        </button>
      </div>
    </>
  );
}
