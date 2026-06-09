import { useEffect, useMemo, useRef, useState } from "react";
import { useTelegram } from "@/lib/telegram";

const ITEM_H = 56;
const VISIBLE = 5;

/* ---------------- click sound (WebAudio, no assets) ---------------- */
let _ac: AudioContext | null = null;
function getAC(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (_ac) return _ac;
  const Ctor =
    (window.AudioContext as typeof AudioContext | undefined) ??
    ((window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext);
  if (!Ctor) return null;
  try { _ac = new Ctor(); } catch { _ac = null; }
  return _ac;
}
function playTick() {
  const ac = getAC(); if (!ac) return;
  if (ac.state === "suspended") void ac.resume().catch(() => {});
  const now = ac.currentTime;
  const dur = 0.035;

  // filtered noise burst
  const bufSize = Math.floor(ac.sampleRate * dur);
  const buf = ac.createBuffer(1, bufSize, ac.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < bufSize; i++) {
    const t = i / bufSize;
    data[i] = (Math.random() * 2 - 1) * Math.pow(1 - t, 3);
  }
  const noise = ac.createBufferSource(); noise.buffer = buf;
  const bp = ac.createBiquadFilter(); bp.type = "bandpass";
  bp.frequency.value = 4200; bp.Q.value = 6;
  const ng = ac.createGain();
  ng.gain.setValueAtTime(0.0001, now);
  ng.gain.exponentialRampToValueAtTime(0.18, now + 0.002);
  ng.gain.exponentialRampToValueAtTime(0.0001, now + dur);
  noise.connect(bp).connect(ng).connect(ac.destination);
  noise.start(now); noise.stop(now + dur);

  // triangle accent
  const osc = ac.createOscillator(); osc.type = "triangle";
  osc.frequency.setValueAtTime(1600, now);
  osc.frequency.exponentialRampToValueAtTime(900, now + dur);
  const og = ac.createGain();
  og.gain.setValueAtTime(0.0001, now);
  og.gain.exponentialRampToValueAtTime(0.08, now + 0.002);
  og.gain.exponentialRampToValueAtTime(0.0001, now + dur);
  osc.connect(og).connect(ac.destination);
  osc.start(now); osc.stop(now + dur);
}

/* ---------------- wheel ---------------- */
function CrownWheel({
  values, index, onIndexChange, ariaLabel,
}: {
  values: number[]; index: number;
  onIndexChange: (i: number) => void; ariaLabel: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const ridgeRef = useRef<HTMLDivElement>(null);
  const lastReported = useRef(index);
  const settleTimer = useRef<number | null>(null);
  const { haptic } = useTelegram();

  useEffect(() => {
    const el = scrollRef.current; if (!el) return;
    const target = index * ITEM_H;
    if (Math.abs(el.scrollTop - target) > 2) el.scrollTo({ top: target });
  }, [index]);

  const onScroll = () => {
    const el = scrollRef.current; if (!el) return;
    if (ridgeRef.current) {
      const deg = (el.scrollTop / ITEM_H) * 30;
      ridgeRef.current.style.backgroundPosition = `0px ${-deg * 0.6}px, 0 0`;
    }
    const i = Math.max(0, Math.min(values.length - 1, Math.round(el.scrollTop / ITEM_H)));
    if (i !== lastReported.current) {
      lastReported.current = i;
      haptic("selection");
      if (typeof navigator !== "undefined" && "vibrate" in navigator) {
        try { navigator.vibrate(8); } catch { /* noop */ }
      }
      playTick();
      onIndexChange(i);
    }
    if (settleTimer.current) window.clearTimeout(settleTimer.current);
    settleTimer.current = window.setTimeout(() => {
      const t = i * ITEM_H;
      if (Math.abs(el.scrollTop - t) > 0.5) el.scrollTo({ top: t, behavior: "smooth" });
    }, 90);
  };

  const padding = (VISIBLE - 1) / 2;

  return (
    <div
      className="relative select-none"
      style={{ height: ITEM_H * VISIBLE, width: 96 }}
      onPointerDown={() => {
        const ac = getAC();
        if (ac && ac.state === "suspended") void ac.resume().catch(() => {});
      }}
    >
      {/* Drum base */}
      <div aria-hidden className="absolute inset-0 rounded-[28px] overflow-hidden shadow-[inset_0_0_0_1px_rgba(255,221,45,0.18),0_10px_28px_-12px_rgba(0,0,0,0.6)]"
        style={{ background: "linear-gradient(90deg, #5a4500 0%, #c79b00 18%, #ffdd2d 50%, #c79b00 82%, #5a4500 100%)" }} />
      {/* Ribbed layer that spins with scroll */}
      <div ref={ridgeRef} aria-hidden
        className="absolute inset-0 rounded-[28px] overflow-hidden pointer-events-none will-change-[background-position]"
        style={{
          backgroundImage: "repeating-linear-gradient(to bottom, rgba(0,0,0,0.55) 0 1px, rgba(255,255,255,0.06) 1px 3px, rgba(0,0,0,0) 3px 7px)",
          backgroundSize: "100% 7px, 100% 100%",
          mixBlendMode: "overlay",
        }} />
      {/* Top/bottom shading */}
      <div aria-hidden className="absolute inset-0 rounded-[28px] pointer-events-none"
        style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 78%, rgba(0,0,0,0.55) 100%)" }} />
      {/* Center slot */}
      <div aria-hidden className="absolute left-2 right-2 pointer-events-none rounded-xl"
        style={{
          top: `calc(50% - ${ITEM_H / 2}px)`, height: ITEM_H,
          background: "linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.04))",
          boxShadow: "inset 0 0 0 1.5px rgba(24,23,15,0.55), 0 0 24px -6px rgba(255,221,45,0.7)",
        }} />
      {/* Scroll surface */}
      <div ref={scrollRef} role="listbox" aria-label={ariaLabel} onScroll={onScroll}
        className="absolute inset-0 overflow-y-scroll no-scrollbar"
        style={{
          scrollSnapType: "y mandatory",
          WebkitMaskImage: "linear-gradient(to bottom, transparent 0, #000 22%, #000 78%, transparent 100%)",
          maskImage: "linear-gradient(to bottom, transparent 0, #000 22%, #000 78%, transparent 100%)",
        }}>
        <div style={{ paddingTop: padding * ITEM_H, paddingBottom: padding * ITEM_H }}>
          {values.map((v, i) => {
            const active = i === index;
            return (
              <div key={v}
                style={{ height: ITEM_H, scrollSnapAlign: "center", scrollSnapStop: "always" }}
                className={`grid place-items-center text-[28px] tabular-nums tracking-tight transition-[transform,opacity,color] duration-150 ${
                  active ? "font-black text-[#18170f] scale-[1.08]" : "font-bold text-[#2a2510]/70 scale-95"
                }`}>
                {String(v).padStart(2, "0")}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function CrownTimePicker({
  value, onChange,
}: { value: string | null; onChange: (t: string) => void }) {
  const hours = useMemo(() => Array.from({ length: 24 }, (_, i) => i), []);
  const minutes = useMemo(() => Array.from({ length: 12 }, (_, i) => i * 5), []);
  const initial = (() => {
    if (value && /^\d{2}:\d{2}$/.test(value)) {
      const [h, m] = value.split(":").map(Number);
      return { h, mIdx: Math.round(m / 5) % 12 };
    }
    return { h: 8, mIdx: 0 };
  })();
  const [h, setH] = useState(initial.h);
  const [mIdx, setMIdx] = useState(initial.mIdx);

  useEffect(() => {
    onChange(`${String(h).padStart(2, "0")}:${String(minutes[mIdx]).padStart(2, "0")}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [h, mIdx]);

  return (
    <div className="px-5">
      <div className="flex items-center justify-center gap-5 py-6">
        <CrownWheel values={hours} index={h} onIndexChange={setH} ariaLabel="Часы" />
        <div className="text-[40px] font-black text-foreground/80 leading-none -mt-1">:</div>
        <CrownWheel values={minutes} index={mIdx} onIndexChange={setMIdx} ariaLabel="Минуты" />
      </div>
      <p className="text-center text-xs text-muted-foreground mt-1">
        Крути колёсики — часы по 1, минуты по 5
      </p>
    </div>
  );
}
