import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import AlertTicker from "../components/AlertTicker";
import { getTickerBulletins } from "../services/api";
import { useAlertStream } from "../hooks/useAlertStream";

/**
 * How often the scrolling warning strip re-fetches its bulletins on its own,
 * as a fallback -- useAlertStream below already re-fetches immediately the
 * moment a new alert actually fires, so this interval mostly just covers
 * bulletins that change for other reasons (edited/resolved elsewhere).
 * See src/services/api.js → getTickerBulletins() (real active alerts)
 */
const TICKER_REFRESH_MS = 5 * 60 * 1000;

export default function DashboardLayout({ title, subtitle, children }) {
  const [bulletins, setBulletins] = useState([]);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const loadBulletins = useCallback(() => {
    // A failed refresh keeps whatever the strip already shows rather than erroring.
    getTickerBulletins().then(setBulletins).catch(() => {});
  }, []);

  useEffect(() => {
    loadBulletins();
    const timer = setInterval(loadBulletins, TICKER_REFRESH_MS);
    return () => clearInterval(timer);
  }, [loadBulletins]);

  // A newly-triggered alert should show up in the scrolling warning strip
  // immediately, not up to 5 minutes later -- this is the "does the
  // dashboard actually update live" moment for a demo.
  useAlertStream(loadBulletins);

  return (
    <div className="flex min-h-screen bg-paper-100 dark:bg-night-950">
      <Sidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
      <div className="flex flex-1 flex-col min-w-0">
        <Topbar title={title} subtitle={subtitle} onMenuClick={() => setMobileNavOpen(true)} />

        {/* Scrolling warning strip — sits directly under the header on every
            page, exactly like the running bar on the IMD rainfall site. */}
        <AlertTicker bulletins={bulletins} />

        <main className="flex-1 p-6">{children}</main>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-paper-200 dark:border-night-700 bg-paper-50 dark:bg-night-900 px-6 py-3 text-xs text-paper-600 dark:text-paper-400">
          <span>© 2026 Landslide Early Warning System</span>
          <Link to="/data-methodology" className="underline decoration-dotted underline-offset-2 hover:text-teal-600">
            Data sources & methodology
          </Link>
        </footer>
      </div>
    </div>
  );
}
