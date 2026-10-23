import { useState } from "react";
import { Bell, BellOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAsyncData } from "../hooks/useAsyncData";
import { getSubscriptionConfig } from "../services/api";
import { isIosBrowserTab, pushSupported, readSubscription, subscribeToArea, unsubscribeFromAlerts } from "../services/push";

const kmBetween = (lat1, lng1, lat2, lng2) =>
  Math.hypot((lat2 - lat1) * 111.32, (lng2 - lng1) * 111.32 * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180));

/**
 * "Get a notification if a warning is raised near here." An opt-in a resident does for their own
 * browser: no account, no phone number. Shown only once the backend says notifications are switched
 * on. One browser watches one area, so subscribing here replaces an earlier area. It is plain about
 * its limits: it needs data, and no notification does not mean safe.
 */
export default function AlertMeCard({ place }) {
  const { t, i18n } = useTranslation();
  const { data: config } = useAsyncData(getSubscriptionConfig);
  const [stored, setStored] = useState(() => readSubscription());
  const [phase, setPhase] = useState("idle"); // idle | working | denied | error
  if (!config || !config.enabled) return null; // off, or the backend could not be reached: not offered

  const here = stored && kmBetween(stored.lat, stored.lng, place.lat, place.lng) < 0.5;
  const supported = pushSupported();

  const turnOn = async () => {
    setPhase("working");
    try {
      const result = await subscribeToArea({ lat: place.lat, lng: place.lng, placeLabel: place.name.slice(0, 120), language: i18n.language, config });
      if (result.status === "denied") return setPhase("denied");
      setStored(readSubscription());
      setPhase("idle");
    } catch {
      setPhase("error");
    }
  };
  const turnOff = async () => {
    setPhase("working");
    try {
      await unsubscribeFromAlerts();
      setStored(null);
      setPhase("idle");
    } catch {
      setPhase("error");
    }
  };

  const buttonClass = "inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60";
  return (
    <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
      <h3 className="mb-2 flex items-center gap-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
        <Bell size={18} className="text-teal-600" />
        {t("alertMe.title", { place: place.name })}
      </h3>
      <p className="text-sm text-paper-600 dark:text-paper-400">{t("alertMe.body", { km: config.defaultRadiusKm })}</p>

      {!supported ? (
        <p className="mt-3 text-sm font-medium text-paper-700 dark:text-paper-300">{t(isIosBrowserTab() ? "alertMe.ios" : "alertMe.unsupported")}</p>
      ) : here ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-risk-low dark:text-risk-lowOn">
            {t("alertMe.on", { place: stored.placeLabel || place.name, km: stored.radiusKm })}
          </span>
          <button
            type="button"
            onClick={turnOff}
            disabled={phase === "working"}
            className={`${buttonClass} border border-paper-200 text-paper-700 hover:bg-paper-50 dark:border-night-700 dark:text-paper-300 dark:hover:bg-night-800`}
          >
            <BellOff size={15} />
            {t("alertMe.stop")}
          </button>
        </div>
      ) : (
        <div className="mt-3">
          {stored && <p className="mb-2 text-xs text-paper-500">{t("alertMe.elsewhere", { place: stored.placeLabel || "-" })}</p>}
          <button type="button" onClick={turnOn} disabled={phase === "working"} className={`${buttonClass} bg-teal-600 text-white hover:bg-teal-700`}>
            <Bell size={15} />
            {phase === "working" ? t("alertMe.working") : t("alertMe.button")}
          </button>
        </div>
      )}

      {phase === "denied" && <p className="mt-2 text-sm text-risk-moderate dark:text-risk-moderateOn">{t("alertMe.denied")}</p>}
      {phase === "error" && <p className="mt-2 text-sm text-risk-high dark:text-risk-highOn">{t("alertMe.error")}</p>}
      <p className="mt-3 text-xs text-paper-500">{t("alertMe.limits")}</p>
    </div>
  );
}
