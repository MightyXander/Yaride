import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { Icon } from "../../components/Icon";
import { BottomActionButton } from "../../components/BottomActionButton";
import { haptic } from "../../telegram/webapp";
import { getDraft, patchDraft } from "../../state/onboarding";

// Шаг 1/3 регистрации: ввод имени (мин. 2 символа).
export function NameInput() {
  const navigate = useNavigate();
  const [name, setName] = useState(() => getDraft().name ?? "");
  const valid = name.trim().length >= 2;

  const next = () => {
    if (!valid) return;
    haptic("medium");
    patchDraft({ name: name.trim() });
    navigate("/onboarding/role");
  };

  return (
    <>
      <Header title="Yaride" centerTitle onBack={() => navigate(-1)} />
      <div className="fixed top-14 left-0 h-1 w-full bg-surface-container z-[60]">
        <div className="h-full bg-primary transition-all duration-500" style={{ width: "33.33%" }} />
      </div>

      <main className="pt-24 pb-32 px-margin-page min-h-screen flex flex-col items-center">
        <div className="w-full max-w-sm flex flex-col items-center">
          <div className="w-full aspect-square max-h-64 rounded-xl overflow-hidden bg-gradient-to-br from-primary-container/30 to-secondary-container/30 mb-6 flex items-center justify-center">
            <Icon name="directions_car" className="text-primary" size={96} />
          </div>
          <div className="inline-flex px-3 py-1 rounded-full bg-primary/10 mb-4">
            <span className="font-label-sm text-label-sm text-primary uppercase tracking-wider">Шаг 1 из 3</span>
          </div>
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface text-center mb-6 px-2">
            Привет! Введи имя — так тебя будут видеть другие участники
          </h2>
        </div>

        <div className="w-full max-w-sm space-y-gutter-stack">
          <div className="relative">
            <label
              className="absolute -top-2.5 left-4 bg-surface px-1 text-label-md font-label-md text-outline"
              htmlFor="name-input"
            >
              Твоё имя
            </label>
            <input
              id="name-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Александр"
              className="w-full h-14 px-4 pt-1 rounded-lg bg-surface-container-low border-2 border-transparent focus:border-primary focus:outline-none text-body-lg font-body-lg text-on-surface placeholder:text-outline/40"
            />
          </div>
          <p className="text-label-md font-label-md text-on-surface-variant/70 px-1">
            Используй реальное имя, чтобы водителю было проще тебя узнать.
          </p>
        </div>
      </main>

      <BottomActionButton label="Далее" onClick={next} disabled={!valid} withArrow />
    </>
  );
}
