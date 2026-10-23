// Browser side of opt-in alerts: ask permission, subscribe this browser to the backend's push
// service, tell the backend which area to watch, and remember the unsubscribe token.
// One browser = one area: subscribing again replaces the earlier area.
import { createSubscription, removeSubscription } from "./api";

const STORAGE_KEY = "ews.alerts.subscription";

export const pushSupported = () =>
  typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

// iPhone and iPad only deliver web push to a site that was added to the Home Screen.
export const isIosBrowserTab = () =>
  typeof navigator !== "undefined" && /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.matchMedia("(display-mode: standalone)").matches;

export function readSubscription() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

function urlBase64ToUint8Array(base64) {
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** { status: "denied" } if the user said no, else { status: "subscribed", ... }. Throws on a server or browser failure. */
export async function subscribeToArea({ lat, lng, placeLabel, language, config }) {
  if (Notification.permission === "denied") return { status: "denied" };
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { status: "denied" };
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const subscription =
    (await registration.pushManager.getSubscription()) ||
    (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(config.publicKey) }));
  const { endpoint, keys } = subscription.toJSON();
  const created = await createSubscription({
    endpoint,
    keys,
    lat,
    lng,
    radius_km: config.defaultRadiusKm,
    place_label: placeLabel,
    language: ["en", "hi", "ne"].includes(language) ? language : "en",
  });
  const stored = { token: created.unsubscribe_token, lat, lng, placeLabel, radiusKm: created.radius_km };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  return { status: "subscribed", ...stored };
}

export async function unsubscribeFromAlerts() {
  const stored = readSubscription();
  if (stored?.token) await removeSubscription(stored.token);
  try {
    const registration = await navigator.serviceWorker.getRegistration("/sw.js");
    await (await registration?.pushManager.getSubscription())?.unsubscribe();
  } catch {
    // The server-side row is already gone; a stale browser subscription can't receive anything.
  }
  localStorage.removeItem(STORAGE_KEY);
}
