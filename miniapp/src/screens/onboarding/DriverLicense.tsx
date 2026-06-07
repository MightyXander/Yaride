import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomActionButton } from "../../components/BottomActionButton";
import { haptic } from "../../telegram/webapp";
import { getDraft } from "../../state/onboarding";
import { api, ApiError } from "../../api/client";
import { useUser } from "../../state/UserContext";

// Срок действия ДД.ММ.ГГГГ → ISO YYYY-MM-DD для бэкенда.
function toIsoDate(ddmmyyyy: string): string {
  const [d, m, y] = ddmmyyyy.split(".");
  return `${y}-${m}-${d}`;
}

// Шаг 3/3 регистрации водителя: серия/номер ВУ + срок действия + авто.
export function DriverLicense() {
  const navigate = useNavigate();
  const { refresh } = useUser();
  const [license, setLicense] = useState("");
  const [expiry, setExpiry] = useState("");
  const [carModel, setCarModel] = useState("");
  const [carColor, setCarColor] = useState("");
  const [carPlate, setCarPlate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onExpiryChange = (raw: string) => {
    let v = raw.replace(/\D/g, "").slice(0, 8);
    if (v.length >= 5) v = `${v.slice(0, 2)}.${v.slice(2, 4)}.${v.slice(4)}`;
    else if (v.length >= 3) v = `${v.slice(0, 2)}.${v.slice(2)}`;
    setExpiry(v);
  };

  const valid = license.trim().length >= 10 && expiry.length === 10;

  const submit = async () => {
    if (!valid || submitting) return;
    haptic("medium");
    setSubmitting(true);
    setError(null);
    try {
      await api.register({
        name: getDraft().name ?? "",
        role: "driver",
        dl_series_number: license.replace(/\s/g, ""),
        dl_valid_until: toIsoDate(expiry),
        car_model: carModel.trim() || undefined,
        car_color: carColor.trim() || undefined,
        car_plate: carPlate.trim() || undefined,
      });
      await refresh();
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось сохранить профиль водителя");
      setSubmitting(false);
    }
  };

  return (
    <>
      <Header title="Yaride" centerTitle onBack={() => navigate(-1)} />
      <div className="fixed top-14 left-0 h-1 w-full bg-surface-container z-[60]">
        <div className="h-full bg-primary transition-all duration-500" style={{ width: "100%" }} />
      </div>

      <main className="pt-24 pb-32 px-margin-page min-h-screen">
        <div className="mb-8">
          <span className="font-label-md text-label-md text-outline mb-2 block">Шаг 3 из 3</span>
          <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Данные водителя</h1>
        </div>

        <div className="mb-8 rounded-xl overflow-hidden bg-gradient-to-br from-primary-container/30 to-surface-container aspect-[16/9] flex items-center justify-center border border-outline-variant/20">
          <Icon name="badge" className="text-primary" size={72} />
        </div>

        <div className="space-y-6">
          <div className="flex flex-col gap-2">
            <label className="font-label-md text-label-md text-on-surface-variant px-1">Серия и номер ВУ</label>
            <div className="bg-surface-container rounded-lg px-4 py-3 flex items-center gap-3 border border-transparent focus-within:border-primary transition-all">
              <Icon name="badge" className="text-outline" />
              <input
                value={license}
                maxLength={14}
                onChange={(e) => setLicense(e.target.value.toUpperCase())}
                placeholder="9916 АВ 123456"
                className="bg-transparent border-none p-0 focus:outline-none w-full font-body-lg text-body-lg text-on-surface placeholder:text-outline/50"
              />
            </div>
            <p className="font-label-sm text-label-sm text-outline px-1">4 цифры, 2 буквы, 6 цифр</p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="font-label-md text-label-md text-on-surface-variant px-1">Срок действия</label>
            <div className="bg-surface-container rounded-lg px-4 py-3 flex items-center gap-3 border border-transparent focus-within:border-primary transition-all">
              <Icon name="calendar_today" className="text-outline" />
              <input
                value={expiry}
                onChange={(e) => onExpiryChange(e.target.value)}
                placeholder="ДД.ММ.ГГГГ"
                inputMode="numeric"
                className="bg-transparent border-none p-0 focus:outline-none w-full font-body-lg text-body-lg text-on-surface placeholder:text-outline/50"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3">
            <p className="font-label-md text-label-md text-on-surface-variant px-1">Автомобиль (необязательно)</p>
            <div className="grid grid-cols-2 gap-3">
              <input
                value={carModel}
                onChange={(e) => setCarModel(e.target.value)}
                placeholder="Kia Rio"
                className="bg-surface-container rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary font-body-md text-body-md text-on-surface placeholder:text-outline/50"
              />
              <input
                value={carColor}
                onChange={(e) => setCarColor(e.target.value)}
                placeholder="Белый"
                className="bg-surface-container rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary font-body-md text-body-md text-on-surface placeholder:text-outline/50"
              />
            </div>
            <input
              value={carPlate}
              onChange={(e) => setCarPlate(e.target.value.toUpperCase())}
              placeholder="У723КВ"
              className="bg-surface-container rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary font-body-md text-body-md text-on-surface placeholder:text-outline/50"
            />
          </div>

          <div className="flex items-start gap-3 p-4 bg-primary/5 rounded-xl border border-primary/10">
            <Icon name="verified_user" className="text-primary text-[20px]" />
            <p className="font-label-md text-label-md text-on-surface-variant">
              Формат ВУ проверяется локально, без запросов в ГИБДД. Данные видны только после подтверждения поездки.
            </p>
          </div>

          {error && <p className="text-center text-label-md font-label-md text-error">{error}</p>}
        </div>
      </main>

      <BottomActionButton
        label={submitting ? "Сохраняем…" : "Сохранить"}
        onClick={submit}
        disabled={!valid || submitting}
        loading={submitting}
      />
    </>
  );
}
