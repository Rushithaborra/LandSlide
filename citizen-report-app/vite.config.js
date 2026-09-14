import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Offline-first field reporting: PS26001 explicitly asks for "low-network/
// offline functionality for remote areas" -- Sikkim's villages are exactly
// that. vite-plugin-pwa (Workbox under the hood) handles both real needs
// with no hand-rolled service-worker or IndexedDB code:
//   1. Precaches the built app shell so the form itself loads with zero
//      network (see workbox.globPatterns below).
//   2. A report submitted with no signal queues in IndexedDB via Workbox's
//      Background Sync and is automatically retried the moment
//      connectivity returns -- see the runtimeCaching entry for POST
//      /reports, and CitizenReportForm.jsx's handling of a queued submit.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBase = env.VITE_API_BASE_URL || "http://localhost:8000";
  const escapedApiBase = apiBase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  return {
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        // The default auto-injected register script is just a bare
        // navigator.serviceWorker.register() with no update-checking loop --
        // "autoUpdate" doesn't actually self-update without it. Disabled
        // here in favor of explicitly calling virtual:pwa-register's own
        // registerSW() in main.jsx, which checks for a new version on load
        // and reloads automatically the moment one activates -- otherwise a
        // returning visitor keeps getting served whatever version of the app
        // was cached on their last visit, even after a new deploy.
        injectRegister: false,
        includeAssets: ["icon.svg"],
        manifest: {
          name: "RESQ Citizen Report",
          short_name: "RESQ Report",
          description: "Report landslide hazards -- cracks, slope movement, blocked roads.",
          theme_color: "#22332B",
          background_color: "#EFEBE1",
          display: "standalone",
          start_url: "/",
          icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
        },
        workbox: {
          globPatterns: ["**/*.{js,css,html,svg}"],
          runtimeCaching: [
            {
              // NetworkOnly (never serve a cached/stale response for a real
              // submission) + backgroundSync: on a failed fetch (offline),
              // Workbox stores the exact request -- including the multipart
              // photo body -- in IndexedDB and replays it automatically once
              // the browser is back online, even if the app has been closed.
              urlPattern: new RegExp(`^${escapedApiBase}/reports$`),
              method: "POST",
              handler: "NetworkOnly",
              options: {
                backgroundSync: {
                  name: "citizen-report-queue",
                  options: { maxRetentionTime: 48 * 60 }, // keep retrying for 48h
                },
              },
            },
          ],
        },
      }),
    ],
  };
});
