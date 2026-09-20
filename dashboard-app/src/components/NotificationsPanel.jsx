import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell, AlertTriangle, CheckCheck } from "lucide-react";
import { getNotifications } from "../services/api";
import { ALERTS_CHANGED_EVENT, agoLabel, alertSentence } from "../utils/localizedText";
import WorsenedNote from "./WorsenedNote";

/**
 * The bell in the top bar: the newest REAL active alerts (api.js
 * getNotifications), with a count of the ones this browser has not opened yet.
 *
 * "Unread" is remembered per browser (localStorage), not per officer: the
 * project has no login yet, so there is no server-side notion of who has read
 * what. New alerts appear live (see ALERTS_CHANGED_EVENT) and start out unread.
 */

const severityTone = {
  High: "text-risk-high dark:text-risk-highOn",
  Moderate: "text-risk-moderate dark:text-risk-moderateOn",
  Low: "text-risk-low dark:text-risk-lowOn",
};

const READ_KEY = "readAlertIds";

function loadReadIds() {
  try {
    return new Set(JSON.parse(localStorage.getItem(READ_KEY)) || []);
  } catch {
    return new Set(); // storage blocked or corrupt: everything simply shows as unread
  }
}

function saveReadIds(ids) {
  try {
    localStorage.setItem(READ_KEY, JSON.stringify([...ids]));
  } catch {
    // ignore -- read state is a convenience, the bell still works without it
  }
}

export default function NotificationsPanel() {
  const { t } = useTranslation();
  const [data, setData] = useState({ items: [], total: 0 });
  const [readIds, setReadIds] = useState(loadReadIds);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const navigate = useNavigate();

  const load = useCallback(() => {
    getNotifications()
      .then((result) => {
        setData(result);
        // Forget ids of alerts that are no longer active, so the stored list can't grow forever.
        setReadIds((prev) => {
          const live = new Set(result.items.map((n) => n.key));
          const kept = new Set([...prev].filter((id) => live.has(id)));
          if (kept.size !== prev.size) saveReadIds(kept);
          return kept.size === prev.size ? prev : kept;
        });
      })
      .catch(() => {}); // keep what is shown if a refresh fails
  }, []);

  useEffect(() => {
    load();
    // New alerts arrive via the layout's live connection (DashboardLayout).
    window.addEventListener(ALERTS_CHANGED_EVENT, load);
    return () => window.removeEventListener(ALERTS_CHANGED_EVENT, load);
  }, [load]);

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

  const markRead = (ids) => {
    setReadIds((prev) => {
      const next = new Set([...prev, ...ids]);
      saveReadIds(next);
      return next;
    });
  };

  // Counts the newest alerts listed in the panel; older active ones are on the Alerts page.
  const unread = data.items.filter((n) => !readIds.has(n.key)).length;
  const badge = unread > 9 ? "9+" : String(unread);

  const openItem = (item) => {
    markRead([item.key]);
    setOpen(false);
    navigate(item.to);
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) load();
        }}
        aria-label={unread ? t("notifications.ariaUnread", { count: unread }) : t("notifications.ariaNone")}
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center rounded-full hover:bg-paper-100 dark:hover:bg-night-800"
      >
        <Bell size={18} className="text-paper-600 dark:text-paper-400" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-risk-high px-1 text-[10px] font-semibold leading-none text-white">
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-[22rem] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-xl border border-paper-200 bg-white shadow-xl dark:border-night-700 dark:bg-night-900">
          <div className="flex items-center justify-between border-b border-paper-200 px-4 py-3 dark:border-night-700">
            <h3 className="font-serif text-sm font-semibold text-ink-900 dark:text-paper-100">{t("notifications.title")}</h3>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markRead(data.items.map((n) => n.key))}
                className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:underline"
              >
                <CheckCheck size={13} />
                {t("notifications.markAll")}
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {data.items.length === 0 && (
              <p className="px-4 py-8 text-center text-sm text-paper-500">{t("notifications.empty")}</p>
            )}

            {data.items.map((n) => {
              const read = readIds.has(n.key);
              return (
                <button
                  key={n.key}
                  type="button"
                  onClick={() => openItem(n)}
                  className={`flex w-full items-start gap-3 border-b border-paper-200 px-4 py-3 text-left last:border-0 hover:bg-paper-50 dark:border-night-700 dark:hover:bg-night-800 ${
                    read ? "opacity-60" : ""
                  }`}
                >
                  <AlertTriangle size={15} className={`mt-0.5 shrink-0 ${severityTone[n.severity] || "text-paper-500"}`} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium text-ink-800 dark:text-paper-200">{n.zone}</span>
                      {!read && <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-risk-high" />}
                    </span>
                    <span className="mt-0.5 block text-xs text-paper-600 dark:text-paper-400">{alertSentence(n.sentence, t)}</span>
                    <WorsenedNote worsenedAt={n.worsenedAt} peakRatio={n.peakRatio} className="mt-0.5 text-[11px]" />
                    <span className="mt-1 block text-[11px] text-paper-500">{agoLabel(n.triggeredAt, t)}</span>
                  </span>
                </button>
              );
            })}
          </div>

          {data.total > data.items.length && (
            <Link
              to="/alerts"
              onClick={() => setOpen(false)}
              className="block border-t border-paper-200 px-4 py-2 text-center text-xs font-medium text-teal-600 hover:underline dark:border-night-700"
            >
              {t("notifications.viewAll", { shown: data.items.length, total: data.total })}
            </Link>
          )}

          <p className="border-t border-paper-200 px-4 py-2 text-[10px] leading-snug text-paper-500 dark:border-night-700">
            {t("notifications.note")}
          </p>
        </div>
      )}
    </div>
  );
}
