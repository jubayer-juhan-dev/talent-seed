import { useEffect, useState } from "react";

/** Animate a number from 0 to `to` (ease-out), or jump straight there when the user prefers reduced motion. */
export function useCountUp(to: number | undefined, ms = 900) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (to == null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(to);
      return;
    }
    const t0 = performance.now();
    let frame = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setValue(Math.round(to * (1 - (1 - k) ** 3)));
      if (k < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [to, ms]);
  return value;
}
