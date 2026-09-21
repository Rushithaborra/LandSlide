import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Bell, Users, CloudRain, ShieldCheck, Search } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import StatCard from "../components/StatCard";
import RiskMap from "../components/RiskMap";
import RiskLegend from "../components/RiskLegend";
import AlertsPanel from "../components/AlertsPanel";
import RainfallChart from "../components/RainfallChart";
import {
  getSummaryStats,
  getActiveAlerts,
  getRainfallTrend,
  getRainfallStatus,
  refreshRainfallIfStale,
} from "../services/api";
import { mapCenter } from "../data/mockData";
import { useRegion } from "../context/RegionContext";
import { agoFromMinutes, dayWord } from "../utils/localizedText";
import { useAlertStream } from "../hooks/useAlertStream";

// A place-name search that hands off to the "Check my area" page -- so a
// visitor's first action on the dashboard can be "is MY village safe?".
function CheckAreaCard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim().length >= 2) navigate(`/check-area?q=${encodeURIComponent(text.trim())}`);
      }}
      className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900"
    >
      <p className="mb-2 text-sm font-medium text-ink-900 dark:text-paper-100">{t("overview.checkAreaTitle")}</p>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper-500" />
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("checkArea.placeholder")}
            aria-label={t("checkArea.label")}
            className="w-full rounded-lg border border-paper-200 bg-paper-50 py-2.5 pl-9 pr-3 text-sm text-paper-700 placeholder:text-paper-500 focus:outline-none focus:ring-2 focus:ring-teal-600/30 dark:border-night-700 dark:bg-night-800 dark:text-paper-300"
          />
        </div>
        <button type="submit" disabled={text.trim().length < 2} className="rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50">
          {t("checkArea.search")}
        </button>
      </div>
    </form>
  );
}

export default function Overview() {
  const { t, i18n } = useTranslation();
  // All of this state is populated through src/services/api.js, which today
  // returns mock data and later will call the real backend. See
  // LINKING_GUIDE.md for the full hookup list.
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [rainfall, setRainfall] = useState([]);
  const [rainfallThreshold, setRainfallThreshold] = useState(null);
  const [loadError, setLoadError] = useState(null);
  // Separate from loadError: getSummaryStats succeeding doesn't mean the
  // other parallel fetches did too -- previously only stats' rejection was
  // ever surfaced, so a failed rainfall fetch (say) silently left that card
  // empty/stale with no indication anything had gone wrong. (The map loads
  // its own data and shows its own retry.)
  const [partialError, setPartialError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  // Minutes since the backend last refreshed rainfall (null = unknown/never).
  const [rainfallAge, setRainfallAge] = useState(null);
  const { state: selectedState } = useRegion();
  // Tracks which state this effect last actually fetched for, so a
  // retryCount bump (a live alert arriving via useAlertStream, or the
  // manual Retry button) can be told apart from a real NER-state switch.
  const lastFetchedState = useRef(selectedState);

  useEffect(() => {
    // Previously each call was a bare .then(setX) with no .catch() -- if any
    // one of these rejected (a transient network blip, the backend briefly
    // restarting mid-deploy), `stats` stayed null forever and the page sat
    // on "Loading overview..." permanently with no error and no way to
    // retry short of a manual refresh. Promise.allSettled + an explicit
    // error state fixes both: a partial failure still unblocks the page,
    // and a full failure shows a real retry button.
    let cancelled = false;
    setLoadError(null);

    // Only reset to the loading state on an actual state switch -- not on
    // every retryCount bump, since useAlertStream fires that on every live
    // alert precisely so existing data stays on screen with no loading
    // flash while the re-fetch happens in the background (see below). A
    // real switch, left un-reset, showed the newly selected state's label
    // next to the PREVIOUS state's stat cards/map/alerts for the few
    // seconds the new state's zones took to load -- reported live.
    if (selectedState !== lastFetchedState.current) {
      setStats(null);
    }
    lastFetchedState.current = selectedState;

    setPartialError(null);

    Promise.allSettled([
      getSummaryStats(selectedState),
      getActiveAlerts(selectedState),
      getRainfallTrend(selectedState),
    ]).then(([statsR, alertsR, rainfallR]) => {
      if (cancelled) return;
      const failedNames = [];
      if (statsR.status === "fulfilled") setStats(statsR.value); else failedNames.push(t("overview.statCards"));
      if (alertsR.status === "fulfilled") setAlerts(alertsR.value); else failedNames.push(t("overview.activeAlerts"));
      if (rainfallR.status === "fulfilled") {
        setRainfall(rainfallR.value.readings);
        setRainfallThreshold(rainfallR.value.threshold);
      } else {
        failedNames.push(t("overview.rainfallTrend"));
      }
      if (statsR.status === "rejected") {
        setLoadError(statsR.reason?.message || "Could not reach the backend");
      } else if (failedNames.length > 0) {
        // stats loaded fine (so the page itself renders), but at least one
        // of the other independent fetches didn't -- surface it instead
        // of silently leaving that section empty/stale.
        setPartialError(failedNames.join(", "));
      }
    });

    return () => {
      cancelled = true;
    };
  }, [retryCount, selectedState]);

  // Re-fetch the moment a new alert actually fires, instead of waiting for
  // the officer to manually refresh -- the stat cards, map markers, and
  // Active Alerts panel all update in place, no loading flash (existing
  // data stays on screen while the re-fetch is in flight).
  useAlertStream(() => setRetryCount((n) => n + 1));

  // Opening the Overview tells the backend "someone is looking"; it refreshes
  // rainfall only if what it has is over an hour old (so any number of viewers
  // costs at most one refresh an hour), then the page re-reads without a flash.
  // Runs once per visit -- a state switch doesn't need another refresh.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await refreshRainfallIfStale();
      if (cancelled) return;
      if (result?.status === "refreshed") setRetryCount((n) => n + 1);
      const status = await getRainfallStatus();
      if (!cancelled) setRainfallAge(status?.age_minutes ?? null);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Card sublines arrive as { key, params } (api.js getSummaryStats); word them here.
  const stateName = (s) => (s ? t(`states.${s}`, { defaultValue: s }) : s);
  const noteText = (note) => t(note.key, { ...note.params, state: stateName(note.params?.state) });

  return (
    <DashboardLayout
      title={t("overview.title")}
      subtitle={t("overview.subtitle")}
    >
      {!stats && loadError ? (
        <div className="rounded-xl border border-risk-high/30 bg-risk-highSoft dark:bg-risk-high/10 p-5">
          <p className="text-sm font-medium text-risk-high">{t("overview.loadErrorTitle")}</p>
          <p className="text-sm text-paper-500 mt-1">{loadError}</p>
          <button
            onClick={() => setRetryCount((n) => n + 1)}
            className="mt-3 text-sm font-medium px-3 py-1.5 rounded-lg bg-risk-high text-white hover:opacity-90"
          >
            {t("overview.retry")}
          </button>
        </div>
      ) : !stats ? (
        <p className="text-sm text-paper-500">{t("overview.loading")}</p>
      ) : (
        <div className="space-y-6">
          {partialError && (
            <div className="rounded-lg border border-risk-moderate/30 bg-risk-moderateSoft dark:bg-risk-moderate/10 px-4 py-2.5 text-xs text-risk-moderate dark:text-risk-moderateOn">
              {t("overview.partialErrorNote", { sections: partialError })}
            </div>
          )}
          {/* Top stat cards */}
          <CheckAreaCard />

          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
            <StatCard
              icon={AlertTriangle}
              iconBg="#f8ebe6"
              iconColor="#b4472f"
              label={t("overview.highRiskZones")}
              value={stats.highRiskZones.value}
              deltaLabel={t(selectedState ? "overview.highRiskDeltaState" : "overview.highRiskDeltaAll", {
                state: stateName(selectedState),
                total: stats.highRiskZones.total.toLocaleString(),
              })}
              trend={stats.highRiskZones.trend}
            />
            <StatCard
              icon={Bell}
              iconBg="#faf0dd"
              iconColor="#c8871d"
              label={t("overview.activeAlerts")}
              value={stats.activeAlerts.value}
              deltaLabel={noteText(stats.activeAlerts.note)}
              trend={stats.activeAlerts.trend}
            />
            <StatCard
              icon={Users}
              iconBg="#e7eef2"
              iconColor="#3a6b82"
              label={t("overview.affectedVillages")}
              value={stats.affectedVillages.value}
              deltaLabel={noteText(stats.affectedVillages.note)}
              trend={stats.affectedVillages.trend}
            />
            <StatCard
              icon={CloudRain}
              iconBg="#e9f2f2"
              iconColor="#15606b"
              label={t("overview.rainfall24h")}
              value={stats.rainfall24h.mm === null ? t("overview.noDataYet") : t("overview.mm", { mm: stats.rainfall24h.mm })}
              deltaLabel={
                stats.rainfall24h.zone ? `${stats.rainfall24h.zone} · ${dayWord(stats.rainfall24h.day, t, i18n.language)}` : t("overview.noZoneYet")
              }
              trend={stats.rainfall24h.trend}
            />
            <StatCard
              icon={ShieldCheck}
              iconBg="#ecf2e8"
              iconColor="#5b8c4f"
              label={t("overview.systemHealth")}
              value={stats.systemHealth.healthy ? "100%" : t("overview.healthDown")}
              deltaLabel={t(stats.systemHealth.healthy ? "overview.healthOk" : "overview.healthBad")}
              trend={stats.systemHealth.trend}
            />
          </div>

          {/* Map + Active alerts */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-stretch">
            <div className="xl:col-span-2 flex flex-col bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-serif font-semibold text-ink-900 dark:text-paper-100 text-[15px]">{t("overview.riskMap")}</h2>
                <span className="text-xs text-paper-500">{selectedState || t("overview.allStates")}</span>
              </div>
              {/* flex-1 + min-h so the map grows to match the Active Alerts
                  panel's height instead of leaving blank space below a fixed
                  420px map, but never shrinks below a usable size when the
                  alerts panel happens to be short. */}
              <div className="relative z-0 flex-1 min-h-[420px]">
                <RiskMap center={mapCenter} state={selectedState} height="100%" />
                <div className="absolute left-3 bottom-3 z-[400]">
                  <RiskLegend />
                </div>
              </div>
            </div>

            <AlertsPanel
              alerts={alerts}
              emptyText={t(
                stats.activeAlerts.value === "—" ? "alerts.alertingOff" : selectedState ? "alerts.emptyForState" : "alertsPanel.none",
                { state: selectedState ? t(`states.${selectedState}`, { defaultValue: selectedState }) : t("states.all") },
              )}
            />
          </div>

          {/* Rainfall trend — full width.
              DRAFT 3: the "Recent Alerts" card that used to sit beside this
              was removed, so the chart now takes the whole row. */}
          <div className="bg-white rounded-xl border border-paper-200 p-5 dark:bg-night-900 dark:border-night-700">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-serif font-semibold text-ink-900 text-[15px] dark:text-paper-100">
                {t("overview.rainfallTrend")}
              </h2>
              <span className="text-xs text-paper-500">
                {rainfallThreshold
                  ? t("overview.dangerThreshold", { value: rainfallThreshold.mm.toFixed(1) })
                  : t("overview.noThresholdConfigured")}
                {rainfallAge !== null && ` · ${t("overview.rainfallUpdated", { age: agoFromMinutes(rainfallAge, t) })}`}
              </span>
            </div>
            <RainfallChart data={rainfall} thresholdMm={rainfallThreshold?.mm ?? null} height={340} />
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
