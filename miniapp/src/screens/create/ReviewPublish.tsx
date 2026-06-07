import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomActionButton } from "../../components/BottomActionButton";
import { api, ApiError } from "../../api/client";
import { useFlow } from "../../state/FlowContext";
import { useUser } from "../../state/UserContext";

// Создание поездки, финал: сводка из flow + комментарий + публикация + модалка успеха.
export function ReviewPublish() {
  const navigate = useNavigate();
  const { flow } = useFlow();
  const { refresh } = useUser();
  const [comment, setComment] = useState(flow.comment);
  const [saveTemplate, setSaveTemplate] = useState(false);
  const [published, setPublished] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = flow.startPointId && flow.endPointId && flow.tripDate && flow.departureTime;

  const publish = async () => {
    if (!ready || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createTrip({
        start_point_id: flow.startPointId!,
        end_point_id: flow.endPointId!,
        trip_date: flow.tripDate!,
        departure_time: flow.departureTime!,
        price_rub: flow.priceRub,
        seats_total: flow.seats,
        comment: comment.trim() || undefined,
      });
      // Сохранение маршрута как шаблона не должно ломать публикацию — ошибку проглатываем.
      if (saveTemplate) {
        try {
          await api.createTemplate({
            start_point_id: flow.startPointId!,
            end_point_id: flow.endPointId!,
            price_rub: flow.priceRub,
            seats_total: flow.seats,
            comment: comment.trim() || undefined,
          });
        } catch {
          /* не критично */
        }
      }
      setPublished(true);
      setSubmitting(false);
      void refresh({ silent: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось опубликовать поездку");
      setSubmitting(false);
    }
  };

  return (
    <>
      <Header title="Проверь поездку" centerTitle onBack={() => navigate(-1)} />

      <main className="pt-20 pb-32 px-margin-page">
        <div className="mb-3">
          <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Шаг 4 из 4</span>
        </div>

        <div className="grid grid-cols-1 gap-4">
          <div className="bg-surface-container-lowest p-padding-card rounded-xl border border-outline-variant/20">
            <div className="flex items-start gap-4">
              <div className="flex flex-col items-center gap-1 py-1">
                <Icon name="radio_button_checked" className="text-primary text-[20px]" />
                <div className="w-0.5 h-10 bg-outline-variant/40 rounded-full" />
                <Icon name="location_on" className="text-secondary text-[20px]" filled />
              </div>
              <div className="flex-1 flex flex-col gap-6">
                <div>
                  <p className="font-label-sm text-label-sm text-outline mb-1">Откуда</p>
                  <p className="font-headline-md text-headline-md-mobile text-on-surface">{flow.startLabel ?? "—"}</p>
                </div>
                <div>
                  <p className="font-label-sm text-label-sm text-outline mb-1">Куда</p>
                  <p className="font-headline-md text-headline-md-mobile text-on-surface">{flow.endLabel ?? "—"}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SummaryTile icon="calendar_today" label="Дата" value={flow.tripDate ?? "—"} />
            <SummaryTile icon="schedule" label="Время" value={flow.departureTime ?? "—"} />
          </div>

          <div className="bg-surface-container-lowest p-padding-card rounded-xl border border-outline-variant/20 flex flex-col gap-4">
            <Row icon="event_seat" label="Свободных мест" value={`${flow.seats}`} valueClass="text-primary" />
            <div className="h-px bg-outline-variant/20 w-full" />
            <Row
              icon="payments"
              label="Цена за место"
              value={`${flow.priceRub} ₽`}
              valueClass="text-secondary font-headline-md text-headline-md-mobile"
            />
          </div>

          <div>
            <p className="font-label-sm text-label-sm text-outline uppercase tracking-wider mb-2 px-1">
              Комментарий (необязательно)
            </p>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value.slice(0, 500))}
              rows={3}
              placeholder="Например: еду через центр, в машине не курим"
              className="w-full p-padding-card rounded-xl bg-surface-container-low border-none text-on-surface font-body-md text-body-md placeholder:text-outline/50 resize-none focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <button
            onClick={() => setSaveTemplate((v) => !v)}
            className="flex items-center gap-3 p-padding-card bg-surface-container-low rounded-xl border border-outline-variant/20 text-left"
          >
            <div
              className={`w-6 h-6 rounded flex items-center justify-center shrink-0 transition-colors ${
                saveTemplate ? "bg-primary text-on-primary" : "border-2 border-outline-variant"
              }`}
            >
              {saveTemplate && <Icon name="check" className="text-[16px]" />}
            </div>
            <div>
              <p className="font-body-md text-body-md text-on-surface">Сохранить как маршрут</p>
              <p className="font-label-sm text-label-sm text-on-surface-variant">
                Чтобы в следующий раз опубликовать в пару нажатий
              </p>
            </div>
          </button>

          {error && <p className="text-center text-label-md font-label-md text-error">{error}</p>}

          <p className="font-label-sm text-label-sm text-outline text-center px-4 mt-2">
            Нажимая «Опубликовать», вы подтверждаете правила сервиса. Плата покрывает бензин и износ, сервис не является такси.
          </p>
        </div>
      </main>

      <BottomActionButton
        label={submitting ? "Публикуем…" : "Опубликовать поездку"}
        onClick={publish}
        disabled={!ready || submitting}
        loading={submitting}
      />

      {published && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100] flex items-center justify-center p-6">
          <div className="bg-surface-container-lowest rounded-xl p-8 w-full max-w-xs flex flex-col items-center text-center">
            <div className="w-16 h-16 bg-secondary-container text-on-secondary-container rounded-full flex items-center justify-center mb-6">
              <Icon name="check_circle" filled className="text-[40px]" />
            </div>
            <h2 className="font-headline-lg text-headline-lg mb-2 text-on-surface">Готово!</h2>
            <p className="font-body-md text-body-md text-on-surface-variant mb-6">
              Поездка опубликована и доступна для поиска.
            </p>
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

function SummaryTile({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="bg-surface-container-lowest p-padding-card rounded-xl border border-outline-variant/20 flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-primary" />
      </div>
      <div>
        <p className="font-label-sm text-label-sm text-outline">{label}</p>
        <p className="font-body-lg text-body-lg font-bold text-on-surface">{value}</p>
      </div>
    </div>
  );
}

function Row({ icon, label, value, valueClass = "" }: { icon: string; label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex justify-between items-center">
      <div className="flex items-center gap-3">
        <Icon name={icon} className="text-outline" />
        <span className="font-body-md text-body-md text-on-surface">{label}</span>
      </div>
      <span className={`font-body-md text-body-md font-bold ${valueClass}`}>{value}</span>
    </div>
  );
}
