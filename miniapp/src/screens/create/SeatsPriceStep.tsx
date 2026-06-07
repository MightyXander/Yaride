import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../../components/Header";
import { ProgressBar, StepCaption } from "../../components/ProgressBar";
import { Icon } from "../../components/Icon";
import { BottomActionButton } from "../../components/BottomActionButton";
import { priceOptions, seatOptions } from "../../data/mock";
import { useFlow } from "../../state/FlowContext";

// Создание поездки, шаг мест и цены: чипы количества мест + рекомендованной цены + своя сумма.
export function SeatsPriceStep() {
  const navigate = useNavigate();
  const { flow, patch } = useFlow();
  const [seats, setSeats] = useState(flow.seats);
  const [price, setPrice] = useState<number | "">(flow.priceRub);

  const next = () => {
    if (price === "" || Number(price) <= 0) return;
    patch({ seats, priceRub: Number(price) });
    navigate("/create/review");
  };

  return (
    <>
      <Header title="Места и цена" centerTitle onBack={() => navigate(-1)} />
      <ProgressBar step={3} total={3} />

      <main className="pt-6 pb-32 px-margin-page min-h-screen flex flex-col gap-8">
        <StepCaption step={3} total={3} />
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Icon name="person" className="text-on-surface-variant" />
            <h2 className="font-headline-md text-headline-md-mobile text-on-surface">Количество мест</h2>
          </div>
          <div className="grid grid-cols-3 gap-gap-chip">
            {seatOptions.map((n) => {
              const active = seats === n;
              return (
                <button
                  key={n}
                  onClick={() => setSeats(n)}
                  className={`flex flex-col items-center justify-center p-4 rounded-xl border transition-all ${
                    active
                      ? "bg-primary text-on-primary border-primary shadow-lg"
                      : "bg-surface-container-low border-outline-variant/20"
                  }`}
                >
                  <span className={`font-headline-lg-mobile text-headline-lg-mobile ${active ? "" : "text-primary"}`}>
                    {n}
                  </span>
                  <span className={`font-label-md text-label-md ${active ? "opacity-90" : "text-on-surface-variant"}`}>
                    мест
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section>
          <div className="flex items-center gap-2 mb-4">
            <Icon name="payments" className="text-on-surface-variant" />
            <h2 className="font-headline-md text-headline-md-mobile text-on-surface">Рекомендуемая цена</h2>
          </div>
          <div className="grid grid-cols-3 gap-gap-chip mb-6">
            {priceOptions.map((p) => {
              const active = price === p;
              return (
                <button
                  key={p}
                  onClick={() => setPrice(p)}
                  className={`flex items-center justify-center py-4 rounded-xl border transition-all ${
                    active
                      ? "bg-primary text-on-primary border-primary shadow-lg"
                      : "bg-surface-container-low border-outline-variant/20 text-on-surface"
                  }`}
                >
                  <span className="font-body-lg text-body-lg">{p}₽</span>
                </button>
              );
            })}
          </div>

          <div className="relative">
            <label className="absolute -top-2.5 left-3 bg-surface px-1 text-label-sm font-label-sm text-outline">
              Своя цена
            </label>
            <div className="flex items-center bg-surface-container-low rounded-xl border border-transparent focus-within:border-primary transition-all overflow-hidden">
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="Введите сумму"
                className="w-full bg-transparent border-none py-4 px-4 focus:outline-none text-body-lg font-body-lg text-on-surface placeholder:text-outline/50"
              />
              <span className="pr-4 font-body-lg text-body-lg text-on-surface-variant">₽</span>
            </div>
          </div>
        </section>
      </main>

      <BottomActionButton
        label="Проверить поездку"
        onClick={next}
        disabled={price === "" || Number(price) <= 0}
        withArrow
      />
    </>
  );
}
