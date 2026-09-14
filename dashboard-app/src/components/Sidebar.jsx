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
  ScrollText,
} from "lucide-react";

const navItems = [
  { to: "/", key: "overview", icon: LayoutDashboard, end: true },
  { to: "/alerts", key: "alerts", icon: Bell },
  { to: "/incidents", key: "incidents", icon: AlertTriangle },
  { to: "/highway-corridors", key: "highwayCorridors", icon: RouteIcon },
  { to: "/emergency-contacts", key: "emergencyContacts", icon: Phone },
  { to: "/authority-contacts", key: "authorityContacts", icon: ShieldAlert },
  { to: "/data-observations", key: "dataObservations", icon: Database },
  { to: "/data-methodology", key: "dataMethodology", icon: ScrollText },
  { to: "/citizen-reports", key: "citizenReports", icon: Users },
  { to: "/help", key: "help", icon: HelpCircle },
];

export default function Sidebar() {
  const { t } = useTranslation();

  return (
    <aside className="hidden md:flex md:w-64 shrink-0 flex-col bg-ink-950 text-paper-300 h-screen sticky top-0">
      <div className="flex items-center gap-2 px-5 h-16 border-b border-white/10">
        <Mountain size={22} className="text-white" strokeWidth={2.2} />
        <span className="text-white font-semibold leading-tight text-[15px]">
          {t("sidebar.appNameLine1")}
          <br />
          {t("sidebar.appNameLine2")}
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {navItems.map(({ to, key, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
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
    </aside>
  );
}
