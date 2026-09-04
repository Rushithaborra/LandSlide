import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import AlertTicker from "../components/AlertTicker";
import { getTickerBulletins } from "../services/api";

/**
 * How often the scrolling warning strip re-fetches its bulletins.
 * 5 minutes is a sensible default for a weather bulletin feed; drop it to
 * 60_000 if the backend team makes the endpoint cheap enough.
 * LINK SPOT I — see src/services/api.js → getTickerBulletins()
 */
const TICKER_REFRESH_MS = 5 * 60 * 1000;

export default function DashboardLayout({ title, subtitle, children }) {
  const [bulletins, setBulletins] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = () => {
      getTickerBulletins().then((data) => {
        if (alive) setBulletins(data);
      });
    };
    load();
    const timer = setInterval(load, TICKER_REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="flex min-h-screen bg-paper-100">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <Topbar title={title} subtitle={subtitle} />

        {/* Scrolling warning strip — sits directly under the header on every
            page, exactly like the running bar on the IMD rainfall site. */}
        <AlertTicker bulletins={bulletins} />

        <main className="flex-1 p-6">{children}</main>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-paper-200 bg-paper-50 px-6 py-3 text-xs text-paper-600">
          <span>© 2026 Landslide Early Warning System</span>
          <span>Data sources: IMD, GSI, ISRO, Open-Meteo</span>
        </footer>
      </div>
    </div>
  );
}
