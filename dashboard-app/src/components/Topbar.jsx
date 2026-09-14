import { useEffect, useState } from "react";
import { PhoneCall, Menu } from "lucide-react";
import { useTranslation } from "react-i18next";
import SearchBox from "./SearchBox";
import StateSelector from "./StateSelector";
import NotificationsPanel from "./NotificationsPanel";
import ThemeToggle from "./ThemeToggle";
import LanguageSwitcher from "./LanguageSwitcher";
import AdminDrawer from "./AdminDrawer";
import { getAdminProfile } from "../services/api";

export default function Topbar({ title, subtitle, onMenuClick }) {
  const { t } = useTranslation();
  // Drawer with the admin's details — opens when the avatar is clicked.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    getAdminProfile().then(setProfile);
  }, []);

  return (
    <header className="h-16 border-b border-paper-200 bg-white flex items-center justify-between gap-4 px-4 sm:px-6 sticky top-0 z-30 dark:border-night-700 dark:bg-night-900">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {/* Sidebar is `hidden md:flex` (see Sidebar.jsx) -- below that
            breakpoint this is the only way to reach navigation at all. */}
        <button
          type="button"
          onClick={onMenuClick}
          aria-label={t("topbar.openMenu")}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-paper-600 hover:bg-paper-100 md:hidden dark:text-paper-400 dark:hover:bg-night-800"
        >
          <Menu size={20} />
        </button>
        <div className="min-w-[96px] flex-1">
          <h1 className="font-serif text-lg font-semibold text-ink-900 leading-none truncate dark:text-paper-100">{title}</h1>
          {subtitle && <p className="text-xs text-paper-600 mt-1 truncate dark:text-paper-400">{subtitle}</p>}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3 lg:gap-4">
        {/* Global search — LINK SPOT M */}
        <SearchBox />

        {/* NER expansion, phase 1 — filters the map/stats/corridors by state */}
        <StateSelector />

        {/* One-touch SOS — real tel: link to India's national emergency
            number, always visible, no page navigation needed to reach it. */}
        <a
          href="tel:112"
          aria-label={t("topbar.sosAriaLabel")}
          className="flex items-center gap-1.5 rounded-lg bg-risk-high px-2.5 py-1.5 text-xs font-semibold text-white hover:opacity-90 sm:px-3"
        >
          <PhoneCall size={14} />
          <span className="hidden sm:inline">{t("topbar.sos")}</span>
        </a>

        {/* Notification bell — LINK SPOT N */}
        <NotificationsPanel />

        {/* Language switcher — left of the theme toggle. Hidden below sm and
            moved into the mobile nav drawer instead (Sidebar.jsx) -- with
            search/state/SOS/bell/avatar all needing room too, this is the
            first thing to relocate rather than shrink into illegibility. */}
        <div className="hidden sm:block">
          <LanguageSwitcher />
        </div>

        {/* Light / dark switch — right of the bell, left of the avatar.
            Same reasoning as the language switcher above. */}
        <div className="hidden sm:block">
          <ThemeToggle />
        </div>

        {/* Avatar opens the admin details drawer */}
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label={t("topbar.openAdminDetails")}
          className="flex items-center gap-2 pl-3 border-l border-paper-200 rounded-r-lg hover:opacity-90 dark:border-night-700"
        >
          <div className="w-8 h-8 rounded-full bg-ink-900 text-white text-xs font-semibold flex items-center justify-center dark:bg-teal-600">
            {profile?.initials || "AD"}
          </div>
          <span className="text-sm font-medium text-paper-700 hidden sm:inline dark:text-paper-300">
            {profile ? profile.fullName.split(" ").slice(-1)[0] : t("topbar.admin")}
          </span>
        </button>
      </div>

      <AdminDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </header>
  );
}
