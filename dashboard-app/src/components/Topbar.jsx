import { useEffect, useState } from "react";
import { PhoneCall } from "lucide-react";
import SearchBox from "./SearchBox";
import StateSelector from "./StateSelector";
import NotificationsPanel from "./NotificationsPanel";
import ThemeToggle from "./ThemeToggle";
import AdminDrawer from "./AdminDrawer";
import { getAdminProfile } from "../services/api";

export default function Topbar({ title, subtitle }) {
  // Drawer with the admin's details — opens when the avatar is clicked.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    getAdminProfile().then(setProfile);
  }, []);

  return (
    <header className="h-16 border-b border-paper-200 bg-white flex items-center justify-between px-6 sticky top-0 z-30 dark:border-night-700 dark:bg-night-900">
      <div>
        <h1 className="font-serif text-lg font-semibold text-ink-900 leading-none dark:text-paper-100">{title}</h1>
        {subtitle && <p className="text-xs text-paper-600 mt-1 dark:text-paper-400">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Global search — LINK SPOT M */}
        <SearchBox />

        {/* NER expansion, phase 1 — filters the map/stats/corridors by state */}
        <StateSelector />

        {/* One-touch SOS — real tel: link to India's national emergency
            number, always visible, no page navigation needed to reach it. */}
        <a
          href="tel:112"
          aria-label="Call the national emergency number, 112"
          className="flex items-center gap-1.5 rounded-lg bg-risk-high px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
        >
          <PhoneCall size={14} />
          SOS 112
        </a>

        {/* Notification bell — LINK SPOT N */}
        <NotificationsPanel />

        {/* Light / dark switch — right of the bell, left of the avatar */}
        <ThemeToggle />

        {/* Avatar opens the admin details drawer */}
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open admin details"
          className="flex items-center gap-2 pl-3 border-l border-paper-200 rounded-r-lg hover:opacity-90 dark:border-night-700"
        >
          <div className="w-8 h-8 rounded-full bg-ink-900 text-white text-xs font-semibold flex items-center justify-center dark:bg-teal-600">
            {profile?.initials || "AD"}
          </div>
          <span className="text-sm font-medium text-paper-700 hidden sm:inline dark:text-paper-300">
            {profile ? profile.fullName.split(" ").slice(-1)[0] : "Admin"}
          </span>
        </button>
      </div>

      <AdminDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </header>
  );
}
