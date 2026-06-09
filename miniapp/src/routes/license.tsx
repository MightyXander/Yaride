import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BottomCTA, Field, Screen, ScreenHeader, Section, TextInput } from "@/components/ui-kit";
import { api, ApiError } from "@/lib/api";
import { isLicenseExpiresValid, isLicenseSeriesValid } from "@/lib/license-validation";
import { meQueryOptions, queryKeys } from "@/lib/queries";
import { useBackButton, useTelegram } from "@/lib/telegram";

export const Route = createFileRoute("/license")({
  component: LicenseScreen,
});

function LicenseScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { haptic } = useTelegram();
  const meQ = useQuery(meQueryOptions());
  const profile = meQ.data?.user;
  const hydrated = useRef(false);

  const [series, setSeries] = useState("");
  const [expires, setExpires] = useState("");
  const [carModel, setCarModel] = useState("");
  const [carColor, setCarColor] = useState("");
  const [carPlate, setCarPlate] = useState("");
  const [seriesTouched, setSeriesTouched] = useState(false);
  const [expiresTouched, setExpiresTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile || hydrated.current) return;
    hydrated.current = true;
    setSeries(profile.dlSeriesNumber ?? "");
    setExpires(profile.dlValidUntil ?? "");
    setCarModel(profile.carModel ?? "");
    setCarColor(profile.carColor ?? "");
    setCarPlate(profile.carPlate ?? "");
  }, [profile]);

  const expiresValid = useMemo(() => isLicenseExpiresValid(expires), [expires]);

  const seriesError =
    seriesTouched && !isLicenseSeriesValid(series) ? "Формат: 9916 АВ 123456" : "";
  const expiresError = expiresTouched && expires && !expiresValid ? "Срок действия ВУ истёк" : "";

  const canSave = isLicenseSeriesValid(series) && expiresValid;

  const saveMut = useMutation({
    mutationFn: () =>
      api.register({
        name: profile?.name ?? "Водитель",
        role: "driver",
        dl_series_number: series.trim().replace(/\s+/g, ""),
        dl_valid_until: expires,
        car_model: carModel.trim() || undefined,
        car_color: carColor.trim() || undefined,
        car_plate: carPlate.trim() || undefined,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.me });
      haptic("success");
      navigate({ to: "/account" });
    },
    onError: (e: Error) => {
      haptic("error");
      setError(e instanceof ApiError ? e.message : "Ошибка сохранения");
    },
  });

  const onSave = useCallback(() => {
    setSeriesTouched(true);
    setExpiresTouched(true);
    setError(null);
    if (!canSave || saveMut.isPending) return;
    haptic("light");
    saveMut.mutate();
  }, [canSave, saveMut, haptic]);

  useBackButton(() => navigate({ to: "/account" }));

  return (
    <Screen>
      <ScreenHeader title="Водительское удостоверение" subtitle="Данные проверяются администратором" />
      {error ? <div className="mx-5 text-sm text-destructive">{error}</div> : null}
      <Section>
        <Field label="Серия и номер" error={seriesError}>
          <TextInput
            value={series}
            onChange={(e) => setSeries(e.target.value.toUpperCase())}
            onBlur={() => setSeriesTouched(true)}
            placeholder="9916 АВ 123456"
          />
        </Field>
        <Field label="Срок действия" error={expiresError}>
          <TextInput
            type="date"
            value={expires}
            onChange={(e) => setExpires(e.target.value)}
            onBlur={() => setExpiresTouched(true)}
          />
        </Field>
        <Field label="Авто (необязательно)">
          <div className="space-y-2">
            <TextInput value={carModel} onChange={(e) => setCarModel(e.target.value)} placeholder="Марка" />
            <TextInput value={carColor} onChange={(e) => setCarColor(e.target.value)} placeholder="Цвет" />
            <TextInput value={carPlate} onChange={(e) => setCarPlate(e.target.value)} placeholder="Номер" />
          </div>
        </Field>
      </Section>
      <BottomCTA
        forceInPage
        text="Сохранить"
        onClick={onSave}
        disabled={!canSave || saveMut.isPending}
      />
    </Screen>
  );
}
