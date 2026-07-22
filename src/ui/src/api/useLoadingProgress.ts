import { useEffect, useState } from "react";

/** Elapsed whole seconds while `active` is true; resets when inactive. */
export function useLoadingProgress(active: boolean): number {
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (!active) {
      setElapsedSec(0);
      return;
    }

    const started = Date.now();
    setElapsedSec(0);
    const timer = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - started) / 1000));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [active]);

  return elapsedSec;
}
