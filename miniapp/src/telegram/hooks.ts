import { useEffect } from "react";
import { getWebApp } from "./webapp";

// Управляет нативной MainButton: показывает с текстом и вешает обработчик,
// прячет при размонтировании. В обычном браузере (без Telegram) — no-op,
// поэтому экраны всегда дублируют действие собственной кнопкой внизу.
export function useMainButton(
  text: string,
  onClick: () => void,
  options: { visible?: boolean; active?: boolean } = {},
): void {
  const { visible = true, active = true } = options;

  useEffect(() => {
    const wa = getWebApp();
    if (!wa) return;
    const btn = wa.MainButton;
    btn.setText(text);
    if (active) btn.enable();
    else btn.disable();
    if (visible) btn.show();
    else btn.hide();
    btn.onClick(onClick);
    return () => {
      btn.offClick(onClick);
      btn.hide();
    };
  }, [text, onClick, visible, active]);
}

// Управляет нативной BackButton: показывает и вешает обработчик возврата.
export function useBackButton(onBack: () => void, visible = true): void {
  useEffect(() => {
    const wa = getWebApp();
    if (!wa) return;
    const btn = wa.BackButton;
    if (visible) btn.show();
    else btn.hide();
    btn.onClick(onBack);
    return () => {
      btn.offClick(onBack);
      btn.hide();
    };
  }, [onBack, visible]);
}
