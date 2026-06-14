import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useMemo, useState } from "react";
import { Car, UserRound } from "lucide-react";
import {
  BottomCTA,
  Card,
  Field,
  Screen,
  StepperHeader,
  TextInput,
} from "@/components/ui-kit";
import { api, ApiError, type Role } from "@/lib/api";
import { isLicenseExpiresValid, isLicenseSeriesValid, normalizeLicenseSeries } from "@/lib/license-validation";
import { queryKeys } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/onboarding")({
  component: Onboarding,
});

type Step = "name" | "role" | "license";

const stepMotion = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
  transition: { type: "spring" as const, stiffness: 380, damping: 32 },
};

function Onboarding() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();

  const [step, setStep] = useState<Step>("name");
  const [name, setName] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const [role, setRole] = useState<Role | null>(null);
  const [series, setSeries] = useState("");
  const [seriesTouched, setSeriesTouched] = useState(false);
  const [expires, setExpires] = useState("");
  const [expiresTouched, setExpiresTouched] = useState(false);
  const [carModel, setCarModel] = useState("");
  const [carColor, setCarColor] = useState("");
  const [carPlate, setCarPlate] = useState("");
  const [error, setError] = useState<string | null>(null);

  const registerMut = useMutation({
    mutationFn: api.register,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.me });
      haptic("success");
      navigate({ to: "/home", replace: true });
    },
    onError: (e: Error) => {
      haptic("error");
      setError(e instanceof ApiError ? e.message : "Ошибка регистрации");
    },
  });

  const nameError = nameTouched && name.trim().length < 2 ? "Минимум 2 символа" : "";
  const seriesError =
    seriesTouched && !isLicenseSeriesValid(series) ? "Формат: 9916 АВ 123456" : "";
  const expiresValid = useMemo(() => isLicenseExpiresValid(expires), [expires]);
  const expiresError = expiresTouched && expires && !expiresValid ? "Срок действия ВУ истёк" : "";

  const totalSteps = role === "driver" ? 3 : 2;
  const stepNumber = step === "name" ? 1 : step === "role" ? 2 : 3;
  const stepLabel = step === "name" ? "Знакомство" : step === "role" ? "Роль" : "Документы";

  const bumpShake = useCallback(() => {
    haptic("error");
  }, [haptic]);

  const submit = useCallback(
    (selectedRole: Role) => {
      setError(null);
      const body: Parameters<typeof api.register>[0] = {
        name: name.trim(),
        role: selectedRole,
      };
      if (selectedRole === "driver") {
        const normalized = normalizeLicenseSeries(series);
        if (!normalized) return;
        body.dl_series_number = normalized;
        body.dl_valid_until = expires;
        if (carModel.trim()) body.car_model = carModel.trim();
        if (carColor.trim()) body.car_color = carColor.trim();
        if (carPlate.trim()) body.car_plate = carPlate.trim();
      }
      registerMut.mutate(body);
    },
    [name, series, expires, carModel, carColor, carPlate, registerMut],
  );

  const onNext = useCallback(() => {
    haptic("light");
    if (step === "name") {
      setNameTouched(true);
      if (name.trim().length < 2) {
        bumpShake();
        return;
      }
      setStep("role");
    } else if (step === "role") {
      if (!role) {
        bumpShake();
        return;
      }
      if (role === "driver") setStep("license");
      else submit("passenger");
    } else if (step === "license") {
      setSeriesTouched(true);
      setExpiresTouched(true);
      if (!isLicenseSeriesValid(series) || !expiresValid) {
        bumpShake();
        return;
      }
      submit("driver");
    }
  }, [step, name, role, series, expiresValid, submit, haptic, bumpShake]);

  const canContinue =
    (step === "name" && name.trim().length >= 2) ||
    (step === "role" && role !== null) ||
    (step === "license" && isLicenseSeriesValid(series) && expiresValid);

  const ctaText =
    step === "role" && role === "passenger"
      ? "Начать пользоваться"
      : step === "license"
        ? "Сохранить"
        : "Далее";

  useBackButton(
    step === "name"
      ? null
      : () => {
          haptic("light");
          if (step === "license") setStep("role");
          else if (step === "role") setStep("name");
        },
  );

  return (
    <Screen>
      <div className="px-5 pt-3 flex items-center justify-end">
        {step === "name" ? (
          <button
            type="button"
            onClick={() => {
              haptic("light");
              navigate({ to: "/home" });
            }}
            className="text-sm font-semibold text-muted-foreground press px-2 py-1"
            data-no-tap-glow
          >
            Пропустить
          </button>
        ) : null}
      </div>
      <StepperHeader step={stepNumber} total={totalSteps} label={stepLabel} />
      {error ? (
        <div className="mx-5 mt-4 rounded-xl bg-destructive/15 text-destructive text-sm p-3">{error}</div>
      ) : null}

      <AnimatePresence mode="wait">
        {step === "name" ? (
          <motion.div key="step-name" className="px-5 pt-8" {...stepMotion}>
            <h1 className="text-[28px] font-bold leading-tight">Привет!</h1>
            <p className="text-muted-foreground mt-2 mb-8">Введи имя — так тебя будут видеть в Yaride.</p>
            <Field label="Имя" error={nameError}>
              <TextInput
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (!nameTouched) setNameTouched(true);
                }}
                placeholder="Алексей"
                autoFocus
                maxLength={40}
                invalid={!!nameError}
                className={nameError ? "animate-shake" : ""}
              />
            </Field>
          </motion.div>
        ) : null}

        {step === "role" ? (
          <motion.div key="step-role" className="px-5 pt-4" {...stepMotion}>
            <h1 className="text-[26px] font-bold leading-tight">Выбери роль</h1>
            <div className="space-y-3 mt-6 list-stagger">
              {(["driver", "passenger"] as const).map((r) => (
                <Card
                  key={r}
                  onClick={() => {
                    setRole(r);
                    haptic("selection");
                  }}
                  className={`!p-4 transition-shadow duration-200 ${role === r ? "ring-brand-selected" : ""}`}
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={`size-12 rounded-xl grid place-items-center transition-colors ${
                        role === r ? "brand-gradient text-brand-foreground" : "bg-accent"
                      }`}
                    >
                      {r === "driver" ? <Car className="size-6" /> : <UserRound className="size-6" />}
                    </div>
                    <div>
                      <div className="text-[17px] font-semibold">{r === "driver" ? "Водитель" : "Пассажир"}</div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </motion.div>
        ) : null}

        {step === "license" ? (
          <motion.div key="step-license" className="px-5 pt-4 space-y-4" {...stepMotion}>
            <h1 className="text-[26px] font-bold">Водительское удостоверение</h1>
            <Field label="Серия и номер" error={seriesError}>
              <TextInput
                value={series}
                onChange={(e) => {
                  setSeries(e.target.value.toUpperCase());
                  if (!seriesTouched) setSeriesTouched(true);
                }}
                placeholder="9916 АВ 123456"
                invalid={!!seriesError}
                className={seriesError ? "animate-shake" : ""}
              />
            </Field>
            <Field label="Срок действия" error={expiresError}>
              <TextInput
                type="date"
                value={expires}
                onChange={(e) => setExpires(e.target.value)}
                onBlur={() => setExpiresTouched(true)}
                invalid={!!expiresError}
                className={expiresError ? "animate-shake" : ""}
              />
            </Field>
            <Field label="Авто (необязательно)" hint="Марка, цвет, номер">
              <div className="space-y-2">
                <TextInput value={carModel} onChange={(e) => setCarModel(e.target.value)} placeholder="Kia Rio" />
                <TextInput value={carColor} onChange={(e) => setCarColor(e.target.value)} placeholder="Белый" />
                <TextInput value={carPlate} onChange={(e) => setCarPlate(e.target.value)} placeholder="У723КВ 76" />
              </div>
            </Field>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <BottomCTA
        forceInPage
        text={ctaText}
        onClick={onNext}
        disabled={!canContinue || registerMut.isPending}
      />
    </Screen>
  );
}
