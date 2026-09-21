import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Download, Info, MapPin, Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { useRegion } from "../context/RegionContext";
import { getLandslideRecords, getLandslideSummary, landslideRecordsCsvUrl, RECORDS_PAGE_SIZE } from "../services/api";

// Activity status as recorded by the survey. Colour only hints; the word is always shown.
const ACTIVITY_STYLE = {
  Active: "bg-risk-highSoft text-risk-high dark:bg-risk-high/20 dark:text-risk-highOn",
  Reactivated: "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn",
};
const NEUTRAL = "bg-paper-100 text-paper-600 dark:bg-night-800 dark:text-paper-400";

/**
 * Historical landslide records from the Geological Survey of India inventories
 * (GET /landslide-records), for the state chosen in the top bar. Real data that
 * replaced the sample incidents. The inventories give a place, coordinates and an
 * activity status -- almost never a date or severity -- so none is shown, and the
 * note on the page says these are past records, not live reports.
 */
export default function Incidents() {
  const { t } = useTranslation();
  const { state } = useRegion();
  const [params] = useSearchParams();
  const [district, setDistrict] = useState("");
  const [activity, setActivity] = useState("");
  const [search, setSearch] = useState(params.get("q") || "");
  const [q, setQ] = useState(params.get("q") || ""); // the search actually applied (on Enter / blur)
  const [page, setPage] = useState(0);

  // A different state has different districts: drop the filters and go back to page 1.
  useEffect(() => {
    setDistrict("");
    setActivity("");
    setPage(0);
  }, [state]);

  const stateName = state ? t(`states.${state}`, { defaultValue: state }) : t("states.all");
  const { data: summary } = useAsyncData(() => getLandslideSummary(state), [state]);
  const { data, error, retry } = useAsyncData(
    () => getLandslideRecords({ state, district, activity, q, page }),
    [state, district, activity, q, page],
  );

  const applySearch = () => {
    setQ(search);
    setPage(0);
  };
  const setFilter = (setter) => (e) => {
    setter(e.target.value);
    setPage(0);
  };

  const notLoaded = summary && summary.total === 0;
  const pages = data ? Math.max(1, Math.ceil(data.total / RECORDS_PAGE_SIZE)) : 1;
  const from = data && data.total > 0 ? page * RECORDS_PAGE_SIZE + 1 : 0;
  const to = data ? Math.min(data.total, (page + 1) * RECORDS_PAGE_SIZE) : 0;

  const select = "rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200";

  return (
    <DashboardLayout title={t("incidents.title")} subtitle={t("incidents.subtitle", { state: stateName })}>
      <div className="mb-4 flex items-start gap-3 rounded-xl border border-paper-200 bg-paper-50 px-4 py-3 dark:border-night-700 dark:bg-night-800">
        <Info size={18} className="mt-0.5 shrink-0 text-teal-600" />
        <p className="text-sm text-paper-700 dark:text-paper-300">{t("incidents.note")}</p>
      </div>

      {notLoaded ? (
        <div className="rounded-xl border border-paper-200 bg-white p-6 text-sm text-paper-600 dark:border-night-700 dark:bg-night-900 dark:text-paper-400">
          {t("incidents.notLoaded", { state: stateName })}
        </div>
      ) : error && !data ? (
        <LoadError message={error} onRetry={retry} />
      ) : (
        <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <div className="relative min-w-[12rem] flex-1">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper-500" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && applySearch()}
                onBlur={applySearch}
                placeholder={t("incidents.searchPlaceholder")}
                aria-label={t("incidents.searchPlaceholder")}
                className={`${select} w-full pl-9`}
              />
            </div>
            <select value={district} onChange={setFilter(setDistrict)} aria-label={t("incidents.district")} className={select}>
              <option value="">{t("incidents.allDistricts")}</option>
              {(summary?.districts || []).map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name} ({d.count})
                </option>
              ))}
            </select>
            <select value={activity} onChange={setFilter(setActivity)} aria-label={t("incidents.activity")} className={select}>
              <option value="">{t("incidents.allActivities")}</option>
              {(summary?.activities || []).map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name} ({a.count})
                </option>
              ))}
            </select>
            {data && data.total > 0 && (
              <a
                href={landslideRecordsCsvUrl({ state, district, activity, q })}
                download
                className="inline-flex items-center gap-1.5 rounded-lg border border-paper-200 px-3 py-2 text-sm font-medium text-teal-600 hover:bg-paper-50 dark:border-night-700 dark:hover:bg-night-800"
              >
                <Download size={15} />
                {t("incidents.download", { count: data.total })}
              </a>
            )}
          </div>

          {!data ? (
            <p className="text-sm text-paper-500">{t("common.loading")}</p>
          ) : data.items.length === 0 ? (
            <p className="text-sm text-paper-500">{t("incidents.noMatch")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-paper-500">
                    <th className="pb-2 font-medium">{t("incidents.place")}</th>
                    {!state && <th className="pb-2 font-medium">{t("incidents.stateCol")}</th>}
                    <th className="pb-2 font-medium">{t("incidents.district")}</th>
                    <th className="pb-2 font-medium">{t("incidents.activity")}</th>
                    <th className="pb-2 font-medium">{t("incidents.check")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => {
                    const title = r.name || t("incidents.unnamed", { district: r.district || stateName });
                    return (
                    <tr key={r.id} className="border-t border-paper-200 align-top dark:border-night-700">
                      <td className="py-2.5 pr-3">
                        <p className="font-medium text-ink-800 dark:text-paper-200">{title}</p>
                        {r.location && r.location !== r.name && <p className="text-xs text-paper-500">{r.location}</p>}
                        {(r.material || r.movement || r.historyNote) && (
                          <p className="mt-0.5 text-xs text-paper-500">
                            {[r.material, r.movement].filter(Boolean).join(" · ")}
                            {r.historyNote ? `${r.material || r.movement ? " — " : ""}${r.historyNote}` : ""}
                          </p>
                        )}
                        {r.slideNo && <p className="mt-0.5 text-[11px] text-paper-400">{r.slideNo}</p>}
                      </td>
                      {!state && <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{t(`states.${r.state}`, { defaultValue: r.state })}</td>}
                      <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{r.district || "—"}</td>
                      <td className="py-2.5 pr-3">
                        <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${ACTIVITY_STYLE[r.activity] || NEUTRAL}`}>{r.activity}</span>
                      </td>
                      <td className="py-2.5">
                        <Link
                          to={`/check-area?lat=${r.lat}&lng=${r.lng}&name=${encodeURIComponent(title)}`}
                          className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg border border-paper-200 px-2.5 py-1.5 text-xs font-medium text-teal-600 hover:bg-paper-50 dark:border-night-700 dark:hover:bg-night-800"
                        >
                          <MapPin size={13} />
                          {t("incidents.checkHere")}
                        </Link>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {data && data.total > 0 && (
            <div className="mt-4 flex items-center justify-between gap-3 text-sm text-paper-600 dark:text-paper-400">
              <span>{t("incidents.showing", { from, to, total: data.total })}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  aria-label={t("incidents.prev")}
                  className="rounded-lg border border-paper-200 p-1.5 disabled:opacity-40 dark:border-night-700"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-xs">{t("incidents.pageOf", { page: page + 1, pages })}</span>
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                  disabled={page >= pages - 1}
                  aria-label={t("incidents.next")}
                  className="rounded-lg border border-paper-200 p-1.5 disabled:opacity-40 dark:border-night-700"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
