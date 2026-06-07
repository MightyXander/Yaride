import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomActionButton } from "../../components/BottomActionButton";

type Threshold = "3.0" | "4.0" | "4.5" | "off";

const OPTIONS: { value: Threshold; label: string; icon: string }[] = [
  { value: "3.0", label: "Не ниже 3.0", icon: "star" },
  { value: "4.0", label: "Не ниже 4.0", icon: "star" },
  { value: "4.5", label: "Не ниже 4.5", icon: "star" },
  { value: "off", label: "Выключить фильтр", icon: "block" },
];

// Настройка минимального рейтинга пассажиров, которым разрешено бронировать (radio-список).
export function RatingThreshold() {
  const navigate = useNavigate();
  const [value, setValue] = useState<Threshold>("4.0");

  return (
    <>
      <Header title="Порог рейтинга" centerTitle onBack={() => navigate(-1)} />

      <main className="pt-20 pb-32 px-margin-page space-y-6">
        <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed mt-2">
          Выберите минимальный рейтинг пассажиров, которые могут бронировать ваши поездки.
        </p>

        <div className="space-y-4">
          {OPTIONS.map((o) => {
            const selected = value === o.value;
            return (
              <button
                key={o.value}
                onClick={() => setValue(o.value)}
                className="w-full flex items-center justify-between p-padding-card bg-surface-container-low rounded-xl border transition-all active:scale-[0.98]"
                style={{ borderColor: selected ? "#006193" : "transparent" }}
              >
                <div className="flex items-center gap-3">
                  <Icon name={o.icon} filled={o.icon === "star"} className={o.icon === "star" ? "text-tertiary" : "text-on-surface-variant"} />
                  <span className="font-body-md text-body-md text-on-surface">{o.label}</span>
                </div>
                <div
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
                    selected ? "border-primary" : "border-outline-variant"
                  }`}
                >
                  {selected && <div className="w-2.5 h-2.5 rounded-full bg-primary" />}
                </div>
              </button>
            );
          })}
        </div>

        <div className="bg-primary-container/10 p-padding-card rounded-xl flex items-start gap-4">
          <Icon name="info" className="text-primary mt-1" />
          <p className="font-label-md text-label-md text-on-primary-container">
            Высокий порог рейтинга помогает найти надёжных попутчиков, но может увеличить время поиска пассажиров.
          </p>
        </div>
      </main>

      <BottomActionButton label="Сохранить" onClick={() => navigate(-1)} />
    </>
  );
}
