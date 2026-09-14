import { useEffect, useRef, useState, useCallback } from "react";

// Every page used to do a bare `fetchFn().then(setState)` with no .catch().
// If the request rejected (a transient network blip, the backend briefly
// restarting mid-deploy, Render's free tier waking from sleep), the page
// just sat there empty or stuck loading forever, with no error and no way
// to recover short of a hard refresh -- that's what happened on both
// Overview and Alerts. This hook centralizes the fix: real error state,
// and a retry that re-runs the same fetch on demand.
export function useAsyncData(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  // Tracks the deps this hook last actually fetched for, so a real deps
  // change (e.g. HighwayCorridors' selected NER state, ZoneDetail's zoneId)
  // can be told apart from a bare retry()/attempt bump.
  const lastDeps = useRef(deps);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    // Reset to null only when a real dependency changed -- not on every
    // retry, since useAlertStream drives retry() on every live alert
    // (Alerts.jsx) specifically so existing data stays on screen with no
    // loading flash while that background re-fetch happens. Left
    // unconditional, a real deps change instead showed the NEW deps' label
    // (e.g. the newly selected state) next to the PREVIOUS deps' data for
    // the few seconds the new fetch took -- reported live on Highway
    // Corridors after switching states.
    const depsChanged =
      deps.length !== lastDeps.current.length || deps.some((d, i) => d !== lastDeps.current[i]);
    if (depsChanged) setData(null);
    lastDeps.current = deps;

    fetchFn()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || "Could not reach the backend");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, error, retry };
}
