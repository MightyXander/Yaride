import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Trash2 } from "lucide-react";
import { CrownTimePicker } from "@/components/crown-time-picker";
import { DistrictStep, GeoStep, RouteDateStep, StopStep } from "@/components/route-pick-steps";
import { YandexRouteButton } from "@/components/yandex-route-card";
import {
  BottomCTA,
  Card,
  Field,
  Screen,
  ScreenHeader,
  Section,
  StepperHeader,
  TextInput,
  formatTripDate,
} from "@/components/ui-kit";
import { api, ApiError, type ApiTemplate } from "@/lib/api";
import {
  clearCreateWizardDraft,
  defaultCreateWizardDraft,
  loadCreateWizardDraft,
  saveCreateWizardDraft,
  type CreateWizardDraft,
} from "@/lib/create-wizard";
import { isActiveDriver } from "@/lib/driver-access";
import {
  districtsQueryOptions,
  meQueryOptions,
  queryKeys,
  templatesQueryOptions,
  tripQueryOptions,
  allStopsQueryOptions,
} from "@/lib/queries";
import { tripHasRouteCoords } from "@/lib/yandex-navigator";
import { hasMapPickSearch, parseMapPickSearch, readPendingMapPick } from "@/lib/map-pick";
import { preloadMapForRoutePick } from "@/lib/preload-map";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/create")({
  validateSearch: (search: Record<string, unknown>) => parseMapPickSearch(search),
  component: CreateScreen,
});

type Step = "start" | "from" | "to" | "date" | "time" | "seats" | "price" | "comment" | "done";
type PickView = "district" | "stop" | "geo";
type WizardMode = "new" | "template";

const NEW_STEP_LABELS: Record<"from" | "to" | "date" | "time" | "seats" | "price" | "comment", string> = {
  from: "Откуда",
  to: "Куда",
  date: "Дата",
  time: "Время",
  seats: "Места",
  price: "Цена",
  comment: "Комментарий",
};

const TEMPLATE_STEP_LABELS: Record<"date" | "time", string> = {
  date: "Дата",
  time: "Время",
};

function CreateScreen() {
  const navigate = useNavigate();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const mapSearch = Route.useSearch();
  const mapPickHandled = useRef(false);
  const meQ = useQuery(meQueryOptions());
  const districtsQ = useQuery(districtsQueryOptions());
  const templatesQ = useQuery({ ...templatesQueryOptions(), enabled: isActiveDriver(meQ.data?.user) });

  useEffect(() => {
    preloadMapForRoutePick(router, queryClient);
  }, [router, queryClient]);

  const initialDraft = loadCreateWizardDraft() ?? defaultCreateWizardDraft();
  const [step, setStep] = useState<Step>(initialDraft.step);
  const [pickView, setPickView] = useState<PickView>("district");
  const [pickDistrict, setPickDistrict] = useState<string | null>(null);
  const [fromPointId, setFromPointId] = useState<number | null>(initialDraft.fromPointId);
  const [fromLabel, setFromLabel] = useState(initialDraft.fromLabel);
  const [toPointId, setToPointId] = useState<number | null>(initialDraft.toPointId);
  const [toLabel, setToLabel] = useState(initialDraft.toLabel);
  const [date, setDate] = useState<string | null>(initialDraft.date);
  const [time, setTime] = useState<string | null>(initialDraft.time);
  const [seats, setSeats] = useState<2 | 3 | 4>(initialDraft.seats);
  const [price, setPrice] = useState<100 | 150 | 200>(initialDraft.price);
  const [comment, setComment] = useState(initialDraft.comment);
  const [wizardMode, setWizardMode] = useState<WizardMode | null>(
    initialDraft.step === "start" ? null : "new",
  );
  const [selectedTemplate, setSelectedTemplate] = useState<ApiTemplate | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const snapshotDraft = (): CreateWizardDraft => ({
    step:
      step === "done"
        ? wizardMode === "template"
          ? "time"
          : "comment"
        : step === "start"
          ? "start"
          : step,
    fromPointId,
    fromLabel,
    toPointId,
    toLabel,
    date,
    time,
    seats,
    price,
    comment,
  });

  const applyDraft = (draft: CreateWizardDraft) => {
    setStep(draft.step);
    setPickView("district");
    setPickDistrict(null);
    setFromPointId(draft.fromPointId);
    setFromLabel(draft.fromLabel);
    setToPointId(draft.toPointId);
    setToLabel(draft.toLabel);
    setDate(draft.date);
    setTime(draft.time);
    setSeats(draft.seats);
    setPrice(draft.price);
    setComment(draft.comment);
  };

  const finishFromPick = (id: number, label: string) => {
    const next: CreateWizardDraft = {
      ...snapshotDraft(),
      fromPointId: id,
      fromLabel: label,
      step: "to",
    };
    saveCreateWizardDraft(next);
    setFromPointId(id);
    setFromLabel(label);
    setPickView("district");
    setPickDistrict(null);
    setStep("to");
  };

  const finishToPick = (id: number, label: string) => {
    const next: CreateWizardDraft = {
      ...snapshotDraft(),
      toPointId: id,
      toLabel: label,
      step: "date",
    };
    saveCreateWizardDraft(next);
    setToPointId(id);
    setToLabel(label);
    setPickView("district");
    setPickDistrict(null);
    setStep("date");
  };

  useLayoutEffect(() => {
    if (mapPickHandled.current) return;
    const pick = readPendingMapPick("create", mapSearch);
    if (!pick || pick.flow !== "create") return;
    mapPickHandled.current = true;

    const base = loadCreateWizardDraft() ?? defaultCreateWizardDraft();
    const next: CreateWizardDraft =
      pick.leg === "from"
        ? {
            ...base,
            fromPointId: pick.pointId,
            fromLabel: pick.label,
            step: "to",
          }
        : {
            ...base,
            fromPointId: pick.fromPointId ?? base.fromPointId,
            fromLabel: pick.fromLabel ?? base.fromLabel,
            toPointId: pick.pointId,
            toLabel: pick.label,
            step: "date",
          };

    saveCreateWizardDraft(next);
    applyDraft(next);

    if (hasMapPickSearch(mapSearch)) {
      navigate({ to: "/create", search: {}, replace: true });
    }
  }, [
    mapSearch.mpLeg,
    mapSearch.mpId,
    mapSearch.mpLabel,
    mapSearch.mpFromId,
    mapSearch.mpFromLabel,
    navigate,
  ]);

  const openMap = (leg: "from" | "to") => {
    haptic("light");
    saveCreateWizardDraft(snapshotDraft());
    navigate({
      to: "/route/map",
      search: {
        leg,
        flow: "create",
        ...(leg === "to" && fromPointId && fromLabel
          ? { fromPointId, fromLabel }
          : {}),
      },
    });
  };

  const createMut = useMutation({
    mutationFn: () =>
      api.createTrip({
        start_point_id: fromPointId!,
        end_point_id: toPointId!,
        trip_date: date!,
        departure_time: time!,
        price_rub: price,
        seats_total: seats,
        comment: comment.trim() || undefined,
      }),
    onSuccess: async (res) => {
      clearCreateWizardDraft();
      setCreatedId(res.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.manageTrips });
      haptic("success");
      setStep("done");
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Ошибка создания"),
  });

  const publishMut = useMutation({
    mutationFn: () =>
      api.publishTemplate(selectedTemplate!.id, {
        trip_date: date!,
        departure_time: time!,
      }),
    onSuccess: async (res) => {
      clearCreateWizardDraft();
      setCreatedId(res.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.manageTrips });
      haptic("success");
      setStep("done");
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Ошибка публикации"),
  });

  const deleteTemplateMut = useMutation({
    mutationFn: (id: number) => api.deleteTemplate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.templates }),
  });

  const user = meQ.data?.user;
  const newSteps = ["from", "to", "date", "time", "seats", "price", "comment"] as const;
  const templateSteps = ["date", "time"] as const;
  const stepNum =
    step === "done"
      ? wizardMode === "template"
        ? templateSteps.length
        : newSteps.length
      : wizardMode === "template"
        ? templateSteps.indexOf(step as (typeof templateSteps)[number]) + 1
        : newSteps.indexOf(step as (typeof newSteps)[number]) + 1;
  const stepLabel =
    wizardMode === "template" && (step === "date" || step === "time")
      ? TEMPLATE_STEP_LABELS[step]
      : step !== "start" && step !== "done" && step in NEW_STEP_LABELS
        ? NEW_STEP_LABELS[step as keyof typeof NEW_STEP_LABELS]
        : "";

  useBackButton(() => {
    haptic("light");
    if (step === "done") {
      clearCreateWizardDraft();
      navigate({ to: "/home" });
      return;
    }
    if (step === "start") {
      navigate({ to: "/home" });
      return;
    }
    if (wizardMode === "template") {
      if (step === "date") {
        setWizardMode(null);
        setSelectedTemplate(null);
        setStep("start");
        return;
      }
      if (step === "time") {
        setStep("date");
        return;
      }
    }
    if (step === "comment") {
      setStep("price");
      return;
    }
    if (step === "from") {
      if (pickView === "stop") {
        setPickView("district");
        setPickDistrict(null);
        return;
      }
      if (pickView === "geo") {
        setPickView("district");
        return;
      }
      if (wizardMode === "new") {
        setStep("start");
        setWizardMode(null);
        return;
      }
      clearCreateWizardDraft();
      navigate({ to: "/home" });
      return;
    }
    if (step === "to") {
      if (pickView === "stop") {
        setPickView("district");
        setPickDistrict(null);
        return;
      }
      setPickView("district");
      setPickDistrict(null);
      setStep("from");
      return;
    }
    const idx = newSteps.indexOf(step as (typeof newSteps)[number]);
    if (idx <= 0) {
      setStep("start");
      setWizardMode(null);
      return;
    }
    setStep(newSteps[idx - 1]!);
  });

  if (!isActiveDriver(user)) {
    return (
      <Screen>
        <ScreenHeader title="Только для водителей" subtitle="Дождитесь одобления заявки администратором" />
      </Screen>
    );
  }

  const doneFromLabel = wizardMode === "template" ? (selectedTemplate?.fromTitle ?? "") : fromLabel;
  const doneToLabel = wizardMode === "template" ? (selectedTemplate?.toTitle ?? "") : toLabel;
  const doneSeats = wizardMode === "template" ? (selectedTemplate?.seatsTotal ?? seats) : seats;
  const donePrice = wizardMode === "template" ? (selectedTemplate?.priceRub ?? price) : price;
  const doneFromPointId =
    wizardMode === "template" ? (selectedTemplate?.startPointId ?? fromPointId!) : fromPointId!;
  const doneToPointId =
    wizardMode === "template" ? (selectedTemplate?.endPointId ?? toPointId!) : toPointId!;

  if (step === "done" && createdId && date && time) {
    return (
      <CreateDoneScreen
        createdId={createdId}
        fromPointId={doneFromPointId}
        toPointId={doneToPointId}
        fromLabel={doneFromLabel}
        toLabel={doneToLabel}
        date={date}
        time={time}
        seats={doneSeats}
        price={donePrice}
        canSaveTemplate={wizardMode === "new"}
        templatePayload={
          wizardMode === "new"
            ? {
                start_point_id: fromPointId!,
                end_point_id: toPointId!,
                price_rub: price,
                seats_total: seats,
                comment: comment.trim() || undefined,
              }
            : undefined
        }
        onManage={() => navigate({ to: "/manage" })}
        onHome={() => navigate({ to: "/home" })}
      />
    );
  }

  return (
    <Screen>
      {step !== "done" && step !== "start" && step !== "from" && step !== "to" && stepLabel ? (
        <StepperHeader
          step={stepNum}
          total={wizardMode === "template" ? templateSteps.length : newSteps.length}
          label={stepLabel}
        />
      ) : null}
      {error ? <div className="mx-5 text-sm text-destructive">{error}</div> : null}
      {step === "start" && (
        <>
          <ScreenHeader title="Создать поездку" subtitle="Шаблон или новый маршрут" />
          <Section>
            <Card
              onClick={() => {
                haptic("light");
                setWizardMode("new");
                setStep("from");
              }}
              className="!p-4"
            >
              <div className="font-semibold">Новый маршрут</div>
              <div className="text-xs text-muted-foreground mt-1">Выбрать остановки, дату и цену</div>
            </Card>
          </Section>
          <Section title="Сохранённые маршруты">
            {templatesQ.isLoading ? (
              <div className="h-24 bg-secondary animate-pulse rounded-xl" />
            ) : (templatesQ.data?.templates ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground px-1">Пока нет шаблонов — создайте поездку и сохраните маршрут.</p>
            ) : (
              <div className="space-y-3">
                {(templatesQ.data?.templates ?? []).map((tpl) => (
                  <Card key={tpl.id} className="!p-4">
                    <button
                      type="button"
                      onClick={() => {
                        haptic("light");
                        setWizardMode("template");
                        setSelectedTemplate(tpl);
                        setDate(null);
                        setTime(null);
                        setStep("date");
                      }}
                      className="w-full text-left"
                    >
                      <div className="font-semibold">
                        {tpl.fromTitle} → {tpl.toTitle}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {tpl.seatsTotal} мест · {tpl.priceRub} ₽
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteTemplateMut.mutate(tpl.id)}
                      className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground"
                    >
                      <Trash2 className="size-3.5" /> Удалить шаблон
                    </button>
                  </Card>
                ))}
              </div>
            )}
          </Section>
        </>
      )}
      {step === "from" && pickView === "district" && (
        <DistrictStep
          title="Откуда едем"
          subtitle="Выбери район посадки"
          districts={districtsQ.data?.districts ?? []}
          loading={districtsQ.isLoading}
          showGeo
          onMap={() => openMap("from")}
          onGeo={() => setPickView("geo")}
          onPick={(d) => {
            setPickDistrict(d);
            setPickView("stop");
          }}
          crumbs={[]}
        />
      )}
      {step === "from" && pickView === "stop" && pickDistrict && (
        <StopStep
          district={pickDistrict}
          title="Остановка посадки"
          crumbs={[pickDistrict]}
          onPick={finishFromPick}
        />
      )}
      {step === "from" && pickView === "geo" && (
        <GeoStep onPick={finishFromPick} onManual={() => setPickView("district")} />
      )}
      {step === "to" && pickView === "district" && (
        <DistrictStep
          title="Куда едем"
          subtitle="Выбери район высадки"
          districts={districtsQ.data?.districts ?? []}
          loading={districtsQ.isLoading}
          onMap={() => openMap("to")}
          onPick={(d) => {
            setPickDistrict(d);
            setPickView("stop");
          }}
          crumbs={[fromLabel, "→"]}
        />
      )}
      {step === "to" && pickView === "stop" && pickDistrict && (
        <StopStep
          district={pickDistrict}
          title="Остановка высадки"
          crumbs={[fromLabel, "→", pickDistrict]}
          onPick={finishToPick}
        />
      )}
      {step === "date" && (
        <RouteDateStep
          title={wizardMode === "template" ? "Когда едем" : "Когда едешь"}
          subtitle={wizardMode === "template" ? "Выбери дату" : "Выбери дату поездки"}
          showMonthNav={wizardMode !== "template"}
          showWeekdayHeaders={wizardMode !== "template"}
          highlightToday={wizardMode !== "template"}
          crumbs={
            wizardMode === "template"
              ? [selectedTemplate?.fromTitle ?? "", "→", selectedTemplate?.toTitle ?? ""]
              : [fromLabel, "→", toLabel]
          }
          onPick={(d) => {
            setDate(d);
            setStep("time");
          }}
        />
      )}
      {step === "time" && (
        <TimePicker
          value={time}
          pending={wizardMode === "template" && publishMut.isPending}
          onPick={(t) => {
            haptic("selection");
            setTime(t);
            if (wizardMode === "template") {
              setError(null);
              publishMut.mutate();
              return;
            }
            setStep("seats");
          }}
        />
      )}
      {step === "seats" && wizardMode === "new" && (
        <>
          <ScreenHeader title="Сколько мест?" subtitle="Считая водителя — не нужно" />
          <ChipRow
            options={[2, 3, 4]}
            value={seats}
            onSelect={setSeats}
            suffix=" мест"
          />
          <BottomCTA
            forceInPage
            text="Далее"
            onClick={() => {
              haptic("light");
              setStep("price");
            }}
          />
        </>
      )}
      {step === "price" && wizardMode === "new" && (
        <>
          <ScreenHeader title="Цена за место" subtitle="Покрывает бензин и износ" />
          <ChipRow
            options={[100, 150, 200]}
            value={price}
            onSelect={setPrice}
            suffix=" ₽"
          />
          <BottomCTA
            forceInPage
            text="Далее"
            onClick={() => {
              haptic("light");
              setStep("comment");
            }}
          />
        </>
      )}
      {step === "comment" && (
        <>
          <ScreenHeader title="Комментарий" subtitle="Необязательно — видят пассажиры" />
          <Section>
            <Field label="Для пассажиров" hint="Например: «Без курения», «Багаж до 1 чемодана»">
              <TextInput
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Дополнительная информация"
                maxLength={500}
              />
            </Field>
          </Section>
          <BottomCTA
            forceInPage
            text="Создать поездку"
            disabled={createMut.isPending}
            onClick={() => {
              haptic("light");
              setError(null);
              createMut.mutate();
            }}
          />
        </>
      )}
    </Screen>
  );
}

function TimePicker({
  value,
  onPick,
  pending,
}: {
  value: string | null;
  onPick: (t: string) => void;
  pending?: boolean;
}) {
  const [draft, setDraft] = useState<string | null>(value);
  return (
    <>
      <ScreenHeader title="Во сколько" subtitle="Крути колёсики — как digital crown" />
      <Section>
        <CrownTimePicker value={value} onChange={setDraft} />
        <button
          type="button"
          onClick={() => draft && onPick(draft)}
          disabled={!draft || pending}
          className="mt-6 w-full h-13 min-h-[52px] rounded-2xl brand-gradient brand-glow text-[#18170f] font-bold text-[16px] press disabled:opacity-40"
        >
          Готово · {draft ?? "--:--"}
        </button>
      </Section>
    </>
  );
}

function CreateDoneScreen({
  createdId,
  fromPointId,
  toPointId,
  fromLabel,
  toLabel,
  date,
  time,
  seats,
  price,
  canSaveTemplate,
  templatePayload,
  onManage,
  onHome,
}: {
  createdId: number;
  fromPointId: number;
  toPointId: number;
  fromLabel: string;
  toLabel: string;
  date: string;
  time: string;
  seats: number;
  price: number;
  canSaveTemplate?: boolean;
  templatePayload?: {
    start_point_id: number;
    end_point_id: number;
    price_rub: number;
    seats_total: number;
    comment?: string;
  };
  onManage: () => void;
  onHome: () => void;
}) {
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const tripQ = useQuery({ ...tripQueryOptions(createdId), enabled: createdId > 0 });
  const stopsQ = useQuery(allStopsQueryOptions());
  const [templateSaved, setTemplateSaved] = useState(false);

  const saveTemplateMut = useMutation({
    mutationFn: () => api.createTemplate(templatePayload!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.templates });
      haptic("success");
      setTemplateSaved(true);
    },
  });

  const routeTarget = useMemo(() => {
    const trip = tripQ.data;
    if (trip && tripHasRouteCoords(trip)) {
      return {
        fromTitle: trip.fromTitle,
        toTitle: trip.toTitle,
        startLat: trip.startLat,
        startLng: trip.startLng,
        endLat: trip.endLat,
        endLng: trip.endLng,
      };
    }
    const stops = stopsQ.data?.stops ?? [];
    const from = stops.find((s) => s.id === fromPointId);
    const to = stops.find((s) => s.id === toPointId);
    if (from && to) {
      return {
        fromTitle: fromLabel,
        toTitle: toLabel,
        startLat: from.lat,
        startLng: from.lng,
        endLat: to.lat,
        endLng: to.lng,
      };
    }
    return { fromTitle: fromLabel, toTitle: toLabel };
  }, [tripQ.data, stopsQ.data, fromPointId, toPointId, fromLabel, toLabel]);

  return (
    <Screen>
      <div className="px-5 pt-10 flex flex-col items-center text-center">
        <div className="size-20 rounded-full bg-success/15 text-success grid place-items-center mb-5">
          <CheckCircle2 className="size-10" />
        </div>
        <h1 className="text-2xl font-bold">Поездка создана</h1>
        <p className="text-sm text-muted-foreground mt-2">Доступна для поиска</p>
      </div>
      <Section>
        <Card className="!p-5 text-left">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-3">
            Детали
          </div>
          <div className="font-semibold text-[16px]">{fromLabel}</div>
          <div className="text-muted-foreground my-1.5">↓</div>
          <div className="font-semibold text-[16px]">{toLabel}</div>
          <div className="mt-4 space-y-2 text-[14px]">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Когда</span>
              <span className="font-medium text-right">
                {formatTripDate(date)}, {time}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Мест</span>
              <span className="font-medium">{seats}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Цена за место</span>
              <span className="font-medium">{price} ₽</span>
            </div>
          </div>
        </Card>
      </Section>
      <Section>
        <div className="space-y-3 max-w-md mx-auto w-full">
          <button
            type="button"
            onClick={onManage}
            className="w-full h-13 min-h-[52px] rounded-2xl brand-gradient brand-glow text-[#18170f] font-bold press"
          >
            Перейти в управление
          </button>
          {canSaveTemplate && templatePayload ? (
            <button
              type="button"
              disabled={templateSaved || saveTemplateMut.isPending}
              onClick={() => saveTemplateMut.mutate()}
              className="w-full h-12 rounded-2xl bg-secondary text-secondary-foreground font-semibold press disabled:opacity-50"
            >
              {templateSaved ? "Маршрут сохранён" : "Сохранить как шаблон"}
            </button>
          ) : null}
          <YandexRouteButton target={routeTarget} />
          <button
            type="button"
            onClick={onHome}
            className="w-full h-12 rounded-2xl bg-secondary text-secondary-foreground font-semibold press"
          >
            На главную
          </button>
        </div>
      </Section>
    </Screen>
  );
}

function ChipRow<T extends number>({
  options,
  value,
  onSelect,
  suffix,
}: {
  options: T[];
  value: T;
  onSelect: (v: T) => void;
  suffix: string;
}) {
  const { haptic } = useTelegram();
  return (
    <Section>
      <div className="flex flex-wrap gap-3">
        {options.map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => {
              haptic("selection");
              onSelect(v);
            }}
            className={`h-14 px-6 rounded-xl font-bold ${
              value === v ? "brand-gradient text-[#18170f]" : "bg-secondary text-secondary-foreground"
            }`}
          >
            {v}
            {suffix}
          </button>
        ))}
      </div>
    </Section>
  );
}
