import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAsyncData } from "../hooks/useAsyncData";
import { getDataSources } from "../services/api";
import { agoLabel } from "../utils/localizedText";

const STATUS_STYLE = {
  connected: "bg-risk-lowSoft text-risk-low",
  stale: "bg-risk-moderateSoft text-risk-moderate",
};
const NEUTRAL = "bg-paper-100 text-paper-600 dark:bg-night-800 dark:text-paper-400";

/**
 * What the running system is connected to (getDataSources): rainfall freshness and the
 * landslide records come from the live API, the SMS / AI / photo rows from which
 * credentials the server has. "Connected" here means set up, not tested this second.
 */
export default function DataObservations() {
  const { t } = useTranslation();
  const { data: sources } = useAsyncData(getDataSources);

  const detail = (d) => t(`dataObservations.detail.${d.key}`, { ...d.params, ago: d.params?.at ? agoLabel(d.params.at, t) : undefined });

  return (
    <DashboardLayout title={t("dataObservations.title")} subtitle={t("dataObservations.subtitle")}>
      <p className="mb-4 text-sm text-paper-600 dark:text-paper-400">{t("dataObservations.note")}</p>
      {!sources ? (
        <p className="text-sm text-paper-500">{t("common.loading")}</p>
      ) : (
        <div className="divide-y divide-paper-200 rounded-xl border border-paper-200 bg-white p-4 dark:divide-night-700 dark:border-night-700 dark:bg-night-900">
          {sources.map((s) => (
            <div key={s.key} className="flex items-center justify-between gap-3 py-3">
              <div>
                <p className="text-sm font-medium text-ink-800 dark:text-paper-200">{t(`dataObservations.rows.${s.key}`)}</p>
                <p className="text-xs text-paper-500">{detail(s.detail)}</p>
              </div>
              <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLE[s.status] || NEUTRAL}`}>
                {t(`dataObservations.status.${s.status}`)}
              </span>
            </div>
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}
