"use client";
import { useEffect, useRef, useState } from "react";

interface AmbientTimerProps {
  active: boolean;
  onExpire?: () => void;
  resetKey: number | string;
}

const DURATION_MS = 90_000;

export default function AmbientTimer({ active, onExpire, resetKey }: AmbientTimerProps) {
  const [progress, setProgress] = useState(0);
  const startRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Reset whenever resetKey or active changes
    setProgress(0);
    startRef.current = null;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    if (!active) return;

    const tick = (now: number) => {
      if (startRef.current === null) startRef.current = now;
      const elapsed = now - startRef.current;
      const pct = Math.min(elapsed / DURATION_MS, 1);
      setProgress(pct);
      if (pct < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        onExpire?.();
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [resetKey, active]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="w-full h-[3px] bg-gray-800 rounded-full overflow-hidden">
      <div
        className="h-full bg-blue-500 rounded-full"
        style={{ width: `${progress * 100}%` }}
      />
    </div>
  );
}
