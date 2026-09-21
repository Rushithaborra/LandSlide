import { CloudRain } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAsyncData } from "../hooks/useAsyncData";
import { getImdWarnings } from "../services/api";
import { agoLabel } from "../utils/localizedText";

const VISIBLE_DISTRICTS = 8;
const OLD_AFTER_MS = 48 * 3600 * 1000;

// IMD's colour codes: 1 red, 2 orange, 3 yellow, 4 green. The colour is always named in words too.
const COLOR_STYLE = {
  1: "bg-risk-highSoft text-risk-high dark:bg-risk-high/20 dark:text-risk-highOn",
  2: "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn",
  3: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
  4: "bg-risk-lowSoft text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn",
};

const ddmm = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const ddmmyyyy = (iso) => `${ddmm(iso)}/${iso.slice(0, 4)}`;

/**
 * The India Meteorological Department's district rain warnings for the next five days, from a
 * snapshot fetched by hand (scripts/push_imd_warnings.py; IMD's key works from one fixed IP only).
 * Rainfall warnings, not landslide alerts, and kept apart from this system's own alerts. Says when
 * IMD issued them and how long ago they were fetched, and tells "IMD lists this state and warns
 * nowhere" apart from "IMD's feed does not list this state".
 */
export default function ImdWarningsPanel({ state, stateName, className = "" }) {
  const { t } = useTranslation();
  const { data } = useAsyncData(() => getImdWarnings(state), [state]);
  if (!data) return null; // loading or unreachable: this panel is supplementary, the page works without it

  const old = data.fetchedAt && Date.now() - new Date(data.fetchedAt).getTime() > OLD_AFTER_MS;
  const shown = data.districts.slice(0, VISIBLE_DISTRICTS);

  let body;
  if (!data.issuedAt) body = <p className="text-sm text-paper-500">{t("imdWarnings.noSnapshot")}</p>;
  else if (data.coveredCount === 0) body = <p className="text-sm text-paper-500">{t("imdWarnings.notListed", { state: stateName })}</p>;
  else if (data.districts.length === 0) body = <p className="text-sm text-paper-500">{t("imdWarnings.none", { count: data.coveredCount })}</p>;
  else
    body = (
      <ul className="space-y-2.5">
        {shown.map((d) => (
          <li key={`${d.state}-${d.district}`} className="text-sm">
            <p className="font-medium text-ink-800 dark:text-paper-200">
              {d.district}
              {!state && <span className="font-normal text-paper-500"> · {t(`states.${d.state}`, { defaultValue: d.state })}</span>}
            </p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {d.days.map((day) => (
                <span key={day.day} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${COLOR_STYLE[day.color] || COLOR_STYLE[4]}`}>
                  {t("imdWarnings.day", { n: day.day, date: ddmm(day.date) })} · {day.kinds.map((k) => t(`imdWarnings.kind.${k}`)).join(" + ")} · {t(`imdWarnings.color.${day.color}`)}
                </span>
              ))}
            </div>
          </li>
        ))}
        {data.districts.length > shown.length && <li className="text-xs text-paper-500">{t("imdWarnings.more", { count: data.districts.length - shown.length })}</li>}
      </ul>
    );

  return (
    <div className={`rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900 ${className}`}>
      <div className="mb-1 flex items-center gap-2">
        <CloudRain size={16} className="text-teal-600" />
        <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("imdWarnings.title")}</h2>
      </div>
      <p className="mb-3 text-xs text-paper-600 dark:text-paper-400">{t("imdWarnings.note")}</p>
      {body}
      {data.issuedAt && (
        <p className="mt-3 text-[11px] text-paper-500">
          {t("imdWarnings.issuedFetched", { date: ddmmyyyy(data.issuedAt), ago: agoLabel(data.fetchedAt, t) })}
          {old && <span className="ml-1 font-medium text-risk-moderate dark:text-risk-moderateOn">{t("imdWarnings.old")}</span>}
        </p>
      )}
    </div>
  );
}
