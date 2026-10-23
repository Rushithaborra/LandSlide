/* Shows landslide-warning notifications pushed by the backend (see src/services/push.js) and
   opens the dashboard when one is tapped. No caching, no offline mode: it exists only for this. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    // A payload we cannot read still deserves a notice rather than silence.
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Landslide warning", {
      body: data.body || "Open the dashboard for details. In danger, call 112.",
      tag: data.tag, // a repeat for the same place replaces the earlier one instead of stacking
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Only ever open a page on this site, whatever the payload says.
  let target = new URL("/", self.location.origin).href;
  try {
    const wanted = new URL(event.notification.data?.url || "/", self.location.origin);
    if (wanted.origin === self.location.origin) target = wanted.href;
  } catch {
    // keep the home page
  }
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const open = windows.find((w) => w.url === target && "focus" in w);
      return open ? open.focus() : self.clients.openWindow(target);
    }),
  );
});
