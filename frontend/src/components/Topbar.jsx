import { Search, Bell } from "lucide-react";

export default function Topbar({ title, subtitle }) {
  return (
    <header className="h-16 border-b border-paper-200 bg-white flex items-center justify-between px-6 sticky top-0 z-10">
      <div>
        <h1 className="font-serif text-lg font-semibold text-ink-900 leading-none">{title}</h1>
        {subtitle && <p className="text-xs text-paper-600 mt-1">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        <div className="relative hidden sm:block">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-paper-500" />
          <input
            type="text"
            placeholder="Search locations, alerts, reports..."
            className="w-72 rounded-lg border border-paper-200 bg-paper-50 pl-9 pr-3 py-2 text-sm text-paper-700 placeholder:text-paper-500 focus:outline-none focus:ring-2 focus:ring-teal-600/30"
          />
        </div>

        <button
          type="button"
          aria-label="Notifications"
          className="relative w-9 h-9 flex items-center justify-center rounded-full hover:bg-paper-100"
        >
          <Bell size={18} className="text-paper-600" />
          <span className="absolute top-1.5 right-2 w-2 h-2 rounded-full bg-risk-high" />
        </button>

        <div className="flex items-center gap-2 pl-3 border-l border-paper-200">
          <div className="w-8 h-8 rounded-full bg-ink-900 text-white text-xs font-semibold flex items-center justify-center">
            AD
          </div>
          <span className="text-sm font-medium text-paper-700 hidden sm:inline">Admin</span>
        </div>
      </div>
    </header>
  );
}
