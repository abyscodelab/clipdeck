import {useCallback, useSyncExternalStore} from 'react';

/** The player's clock, kept out of React state so only the pieces that need it re-render. */
let t = 0;
const subs = new Set<() => void>();
export const timeStore = {
  set(ms: number) { t = ms; subs.forEach((f) => f()); },
  get: () => t,
  sub(f: () => void) { subs.add(f); return () => { subs.delete(f); }; },
};

/** The index of the page showing at the current time (re-renders only when it changes). */
export function useLiveIndex(starts: number[], ends: number[]): number {
  const snap = useCallback(() => {
    const now = timeStore.get();
    for (let i = 0; i < starts.length; i++) if (now >= starts[i] && now < (starts[i + 1] ?? ends[i] + 400)) return i;
    return -1;
  }, [starts, ends]);
  return useSyncExternalStore(timeStore.sub, snap);
}
