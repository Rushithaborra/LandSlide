import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Map,
  Bell,
  FileText,
  AlertTriangle,
  Database,
  Users,
  Settings,
  HelpCircle,
  Mountain,
  CheckCircle2,
} from "lucide-react";

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/live-map", label: "Live Map", icon: Map },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/data-observations", label: "Data & Observations", icon: Database },
  { to: "/citizen-reports", label: "Citizen Reports", icon: Users },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/help", label: "Help & Docs", icon: HelpCircle },
];

export default function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-64 shrink-0 flex-col bg-ink-950 text-paper-300 h-screen sticky top-0">
      <div className="flex items-center gap-2 px-5 h-16 border-b border-white/10">
        <Mountain size={22} className="text-white" strokeWidth={2.2} />
        <span className="text-white font-semibold leading-tight text-[15px]">
          Landslide
          <br />
          Early Warning
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon, end }) => (
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
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="m-3 rounded-xl bg-white/5 p-4 text-sm">
        <div className="flex items-center gap-2 text-[#9ec48f] font-medium">
          <CheckCircle2 size={16} />
          System Status
        </div>
        <p className="mt-2 text-white font-semibold">Operational</p>
        <p className="mt-1 text-xs text-paper-400/80 leading-snug">
          All systems are running normally
        </p>
      </div>
    </aside>
  );
}
