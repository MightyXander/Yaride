import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomNav } from "../../components/BottomNav";
import { api, type ApiTemplate } from "../../api/client";
import { useFlow } from "../../state/FlowContext";
import { haptic } from "../../telegram/webapp";

// Старт создания поездки: быстрая публикация из сохранённого маршрута или новый маршрут с нуля.
export function CreateStart() {
  const navigate = useNavigate();
  const { reset, patch } = useFlow();
  const [templates, setTemplates] = useState<ApiTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadTemplates = useCallback(() => {
    setTemplatesLoading(true);
    setTemplatesError(null);
    api
      .templates()
      .then((res) => setTemplates(res.templates))
      .catch((e: unknown) => {
        setTemplates([]);
        setTemplatesError(e instanceof Error ? e.message : "Не удалось загрузить маршруты");
      })
      .finally(() => setTemplatesLoading(false));
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const newRoute = () => {
    haptic("light");
    reset("create");
    navigate("/route/district?mode=create&leg=start");
  };

  const publishFrom = (t: ApiTemplate) => {
    haptic("light");
    reset("create");
    patch({
      templateId: t.id,
      startPointId: t.startPointId,
      endPointId: t.endPointId,
      startLabel: t.fromTitle,
      endLabel: t.toTitle,
      priceRub: t.priceRub,
      seats: t.seatsTotal,
      comment: t.comment ?? "",
    });
    navigate("/create/publish");
  };

  const remove = async (id: number) => {
    setDeletingId(id);
    try {
      await api.deleteTemplate(id);
      loadTemplates();
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <>
      <Header title="Создать поездку" onBack={() => navigate("/")} />

      <main className="pt-20 pb-24 px-margin-page min-h-screen flex flex-col gap-6">
        <button
          onClick={newRoute}
          className="w-full flex items-center gap-4 bg-primary text-on-primary p-padding-card rounded-xl active:scale-[0.98] transition-transform shadow-lg shadow-primary/20"
        >
          <div className="w-12 h-12 rounded-full bg-on-primary/20 flex items-center justify-center shrink-0">
            <Icon name="add_road" />
          </div>
          <div className="text-left">
            <p className="font-headline-md text-headline-md-mobile font-bold">Новый маршрут</p>
            <p className="font-label-md text-label-md opacity-90">Выбрать точки на карте районов</p>
          </div>
        </button>

        <section>
          <h3 className="font-label-md text-label-md text-outline mb-3 uppercase tracking-widest">Мои маршруты</h3>
          {templatesLoading ? (
            <div className="flex items-center gap-2 py-4 text-on-surface-variant">
              <Icon name="progress_activity" className="animate-spin text-primary" />
              <span className="font-body-md text-body-md">Загружаем маршруты…</span>
            </div>
          ) : templatesError ? (
            <p className="font-body-md text-body-md text-on-surface-variant">
              {templatesError}. Можно создать поездку через «Новый маршрут».
            </p>
          ) : templates.length === 0 ? (
            <p className="font-body-md text-body-md text-on-surface-variant">
              Сохрани маршрут при создании поездки — потом сможешь публиковать его в пару нажатий.
            </p>
          ) : (
            <div className="flex flex-col gap-gutter-stack">
              {templates.map((t) => (
                <div
                  key={t.id}
                  className="bg-surface-container-lowest rounded-xl p-padding-card border border-outline-variant/20 flex items-center gap-3"
                >
                  <button onClick={() => publishFrom(t)} className="flex-1 min-w-0 text-left active:opacity-70">
                    <p className="font-body-lg text-body-lg text-on-surface truncate">
                      {t.fromTitle} <Icon name="arrow_forward" className="text-[14px] text-outline align-middle" /> {t.toTitle}
                    </p>
                    <p className="font-label-md text-label-md text-on-surface-variant">
                      {t.priceRub} ₽ · {t.seatsTotal} мест
                    </p>
                  </button>
                  <button
                    onClick={() => publishFrom(t)}
                    className="shrink-0 h-9 px-3 rounded-lg bg-primary/10 text-primary font-label-md text-label-md"
                  >
                    Опубликовать
                  </button>
                  <button
                    onClick={() => remove(t.id)}
                    disabled={deletingId === t.id}
                    className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-error active:bg-error/10"
                  >
                    <Icon name={deletingId === t.id ? "progress_activity" : "delete"} className={deletingId === t.id ? "animate-spin" : ""} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <BottomNav />
    </>
  );
}
