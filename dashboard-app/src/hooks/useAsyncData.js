import { useEffect, useState, useCallback } from "react";

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

  useEffect(() => {
    let cancelled = false;
    setError(null);
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
