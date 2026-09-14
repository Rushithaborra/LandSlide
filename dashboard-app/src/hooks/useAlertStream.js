import { useEffect, useRef } from "react";
import { ALERT_STREAM_URL } from "../services/api";

/**
 * Subscribes to GET /alerts/stream (Server-Sent Events) and calls `onAlert`
 * with each newly-triggered alert the moment the backend sees it -- no
 * manual refresh, no waiting out a polling interval. Built on the browser's
 * native EventSource: it reconnects automatically on a dropped connection
 * (e.g. Render's free tier cold-restarting), so there's no reconnect logic
 * to hand-roll here.
 *
 * `onAlert` is kept in a ref rather than an effect dependency so a page
 * doesn't tear down and reopen the connection every time its own callback
 * identity changes (e.g. a new closure each render).
 */
export function useAlertStream(onAlert) {
  const onAlertRef = useRef(onAlert);
  useEffect(() => {
    onAlertRef.current = onAlert;
  });

  useEffect(() => {
    const source = new EventSource(ALERT_STREAM_URL);
    source.onmessage = (event) => {
      try {
        const alert = JSON.parse(event.data);
        onAlertRef.current?.(alert);
      } catch {
        // Malformed payload -- ignore this one event rather than tearing
        // down a connection that's otherwise working fine.
      }
    };
    return () => source.close();
  }, []);
}
