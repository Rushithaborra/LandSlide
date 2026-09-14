import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  Bell,
  AlertTriangle,
  Route as RouteIcon,
  Phone,
  ShieldAlert,
  Database,
  Users,
  HelpCircle,
  Mountain,
  CheckCircle2,
  X,
} from "lucide-react";
import LanguageSwitcher from "./LanguageSwitcher";
import ThemeToggle from "./ThemeToggle";

const navItems = [
  { to: "/", key: "overview", icon: LayoutDashboard, end: true },
  { to: "/alerts", key: "alerts", icon: Bell },
  { to: "/incidents", key: "incidents", icon: AlertTriangle },
  { to: "/highway-corridors", key: "highwayCorridors", icon: RouteIcon },
  { to: "/emergency-contacts", key: "emergencyContacts", icon: Phone },
  { to: "/authority-contacts", key: "authorityContacts", icon: ShieldAlert },
  { to: "/data-observations", key: "dataObservations", icon: Database },
  { to: "/citizen-reports", key: "citizenReports", icon: Users },
  { to: "/help", key: "help", icon: HelpCircle },
];

// Shared between the always-present desktop sidebar and the mobile drawer
// below, so both stay in sync off one nav list instead of two copies.
function SidebarContent({ onNavigate, quickSettings = false }) {
  const { t } = useTranslation();

  return (
    <>
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {navItems.map(({ to, key, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-white/10 text-white font-medium"
                  : "text-paper-400 hover:bg-white/5 hover:text-paper-100"
              }`
            }
          >
            <Icon size={18} strokeWidth={2} />
            {t(`sidebar.${key}`)}
          </NavLink>
        ))}
      </nav>

      {/* Language + theme controls live in the Topbar at sm and up; below
          that they don't fit alongside search/state/SOS/bell/avatar, so the
          mobile drawer is where they actually live instead of disappearing. */}
      {quickSettings && (
        <div className="mx-3 flex items-center justify-between gap-2 rounded-xl bg-white/5 px-3 py-2 text-paper-300 [&_button]:text-paper-300 [&_svg]:text-paper-300 [&_select]:text-paper-100">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      )}

      <div className="m-3 rounded-xl bg-white/5 p-4 text-sm">
        <div className="flex items-center gap-2 text-[#9ec48f] font-medium">
          <CheckCircle2 size={16} />
          {t("sidebar.systemStatus")}
        </div>
        <p className="mt-2 text-white font-semibold">{t("sidebar.operational")}</p>
        <p className="mt-1 text-xs text-paper-400/80 leading-snug">
          {t("sidebar.systemsNormal")}
        </p>
      </div>
    </>
  );
}

// mobileOpen/onMobileClose drive a slide-in drawer below md -- the sidebar
// itself is `hidden md:flex` and has no other way to reach navigation on a
// phone-width screen otherwise. Topbar's hamburger button (md:hidden, the
// mirror image of this) opens it.
export default function Sidebar({ mobileOpen = false, onMobileClose }) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e) => e.key === "Escape" && onMobileClose?.();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [mobileOpen, onMobileClose]);

  return (
    <>
      <aside className="hidden md:flex md:w-64 shrink-0 flex-col bg-ink-950 text-paper-300 h-screen sticky top-0">
        <div className="flex items-center gap-2 px-5 h-16 border-b border-white/10">
          <Mountain size={22} className="text-white" strokeWidth={2.2} />
          <span className="text-white font-semibold leading-tight text-[15px]">
            {t("sidebar.appNameLine1")}
            <br />
            {t("sidebar.appNameLine2")}
          </span>
        </div>
        <SidebarContent />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="presentation">
          <div
            className="absolute inset-0 bg-ink-950/60"
            onClick={onMobileClose}
            aria-hidden="true"
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label={`${t("sidebar.appNameLine1")} ${t("sidebar.appNameLine2")}`}
            className="relative flex h-full w-72 max-w-[85vw] flex-col bg-ink-950 text-paper-300 shadow-2xl"
          >
            <div className="flex items-center justify-between gap-2 px-5 h-16 border-b border-white/10">
              <div className="flex items-center gap-2">
                <Mountain size={22} className="text-white" strokeWidth={2.2} />
                <span className="text-white font-semibold leading-tight text-[15px]">
                  {t("sidebar.appNameLine1")}
                  <br />
                  {t("sidebar.appNameLine2")}
                </span>
              </div>
              <button
                type="button"
                onClick={onMobileClose}
                aria-label={t("topbar.closeMenu")}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-paper-400 hover:bg-white/10 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>
            <SidebarContent onNavigate={onMobileClose} quickSettings />
          </aside>
        </div>
      )}
    </>
  );
}
