import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, AlertTriangle, CheckCheck } from "lucide-react";
import { getNotifications, markNotificationsRead } from "../services/api";

/**
 * ============================================================================
 *  NOTIFICATIONS  (NEW IN DRAFT 5)
 * ============================================================================
 * The bell in the top bar. Shows how many alerts the officer has not read yet,
 * and opens a panel listing them.
 *
 * LINK SPOT N (src/services/api.js)
 *   getNotifications()        -> GET  /api/notifications
 *   markNotificationsRead()   -> POST /api/notifications/read
 *
 * ONE HONEST LIMITATION: "unread" means unread BY A PARTICULAR OFFICER, and
 * this project has no login yet. So today every visitor sees the same three
 * unread items, and "Mark all as read" only lasts until the page is reloaded.
 * Once authentication is added, the same code becomes properly personal with
 * no changes here — the backend simply returns that officer's own list.
 * ============================================================================
 */

const severityTone = {
  High: "text-risk-high dark:text-risk-highOn",
  Moderate: "text-risk-moderate dark:text-risk-moderateOn",
  Low: "text-risk-low dark:text-risk-lowOn",
};

export default function NotificationsPanel() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    getNotifications().then(setItems);
  }, []);

  // Close on click-away and on Escape.
  useEffect(() => {
    const onClickAway = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClickAway);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickAway);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const unread = items.filter((n) => !n.read).length;

  const handleMarkAll = async () => {
    await markNotificationsRead();
    setItems((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const openItem = (item) => {
    setItems((prev) =>
      prev.map((n) => (n.id === item.id ? { ...n, read: true } : n))
    );
    setOpen(false);
    navigate(item.to);
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={
          unread ? `Notifications, ${unread} unread` : "Notifications, none unread"
        }
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center rounded-full hover:bg-paper-100 dark:hover:bg-night-800"
      >
        <Bell size={18} className="text-paper-600 dark:text-paper-400" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-risk-high px-1 text-[10px] font-semibold leading-none text-white">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[22rem] overflow-hidden rounded-xl border border-paper-200 bg-white shadow-xl dark:border-night-700 dark:bg-night-900">
          <div className="flex items-center justify-between border-b border-paper-200 px-4 py-3 dark:border-night-700">
            <h3 className="font-serif text-sm font-semibold text-ink-900 dark:text-paper-100">
              Notifications
            </h3>
            {unread > 0 && (
              <button
                type="button"
                onClick={handleMarkAll}
                className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:underline"
              >
                <CheckCheck size={13} />
                Mark all as read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 && (
              <p className="px-4 py-8 text-center text-sm text-paper-500">
                Nothing to show.
              </p>
            )}

            {items.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => openItem(n)}
                className={`flex w-full items-start gap-3 border-b border-paper-200 px-4 py-3 text-left last:border-0 hover:bg-paper-50 dark:border-night-700 dark:hover:bg-night-800 ${
                  n.read ? "opacity-60" : ""
                }`}
              >
                <AlertTriangle
                  size={15}
                  className={`mt-0.5 shrink-0 ${severityTone[n.severity] || "text-paper-500"}`}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium text-ink-800 dark:text-paper-200">
                      {n.title}
                    </span>
                    {!n.read && (
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-risk-high" />
                    )}
                  </span>
                  <span className="mt-0.5 block text-xs text-paper-600 dark:text-paper-400">
                    {n.detail}
                  </span>
                  <span className="mt-1 block text-[11px] text-paper-500">
                    {n.timeAgo}
                  </span>
                </span>
              </button>
            ))}
          </div>

          <p className="border-t border-paper-200 px-4 py-2 text-[10px] leading-snug text-paper-500 dark:border-night-700">
            Read/unread becomes personal to each officer once login is added.
          </p>
        </div>
      )}
    </div>
  );
}
