import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomActionButton } from "../../components/BottomActionButton";
import { haptic } from "../../telegram/webapp";
import type { Role } from "../../data/types";
import { getDraft, patchDraft } from "../../state/onboarding";
import { api, ApiError } from "../../api/client";
import { useUser } from "../../state/UserContext";

// Шаг 2/3 регистрации: выбор роли водитель/пассажир.
export function RoleSelection() {
  const navigate = useNavigate();
  const { refresh } = useUser();
  const [role, setRole] = useState<Role | null>(() => getDraft().role ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const next = async () => {
    if (!role || submitting) return;
    haptic("medium");
    patchDraft({ role });
    if (role === "driver") {
      navigate("/onboarding/license");
      return;
    }
    // Пассажир регистрируется сразу — данные ВУ не нужны.
    setSubmitting(true);
    setError(null);
    try {
      await api.register({ name: getDraft().name ?? "", role: "passenger" });
      await refresh();
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось сохранить профиль");
      setSubmitting(false);
    }
  };

  return (
    <>
      <Header title="Yaride" centerTitle onBack={() => navigate(-1)} />
      <div className="fixed top-14 left-0 h-1 w-full bg-surface-container z-[60]">
        <div className="h-full bg-primary transition-all duration-500" style={{ width: "66.66%" }} />
      </div>

      <main className="pt-24 pb-32 px-margin-page min-h-screen flex flex-col">
        <p className="text-center text-label-sm font-label-sm text-on-surface-variant uppercase tracking-wider mb-4">
          Шаг 2 из 3
        </p>
        <h2 className="font-headline-lg text-headline-lg text-on-surface text-center mb-8">Выбери роль</h2>

        <div className="space-y-gutter-stack">
          <RoleCard
            icon="directions_car"
            title="Водитель"
            subtitle="Создаю поездки, беру попутчиков"
            selected={role === "driver"}
            onClick={() => setRole("driver")}
          />
          <RoleCard
            icon="person"
            title="Пассажир"
            subtitle="Ищу поездки и бронирую места"
            selected={role === "passenger"}
            onClick={() => setRole("passenger")}
          />
        </div>

        <p className="text-center text-label-md font-label-md text-on-surface-variant/70 mt-6 px-6">
          Плата покрывает бензин и износ, сервис не является такси
        </p>

        {error && <p className="text-center text-label-md font-label-md text-error mt-2">{error}</p>}
      </main>

      <BottomActionButton
        label={submitting ? "Сохраняем…" : "Далее"}
        onClick={next}
        disabled={!role || submitting}
        loading={submitting}
      />
    </>
  );
}

function RoleCard({
  icon,
  title,
  subtitle,
  selected,
  onClick,
}: {
  icon: string;
  title: string;
  subtitle: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl p-padding-card border-2 transition-all active:scale-[0.98] ${
        selected
          ? "border-primary bg-primary-fixed/30"
          : "border-transparent bg-surface-container-low"
      }`}
    >
      <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
        <Icon name={icon} className="text-primary" />
      </div>
      <p className="font-headline-md text-headline-md text-on-surface mb-1">{title}</p>
      <p className="font-body-md text-body-md text-on-surface-variant">{subtitle}</p>
    </button>
  );
}
