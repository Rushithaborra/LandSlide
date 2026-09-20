import { Building2, MapPin, Phone } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAsyncData } from "../hooks/useAsyncData";
import { getSurroundings } from "../services/api";

/**
 * What lies around a road stretch: named villages/towns within a few km, and the
 * nearest hospital, clinic, police and fire station. From a downloaded
 * OpenStreetMap snapshot (GET /zones/{id}/surroundings). Deliberately modest:
 * the caution at the bottom says what this is NOT -- no cut-off analysis, no
 * rescue time -- because the data has neither and inventing them would be worse.
 */
export default function SurroundingsPanel({ zoneId }) {
  const { t, i18n } = useTranslation();
  const { data, error } = useAsyncData(() => getSurroundings(zoneId), [zoneId]);

  const kind = (k) => t(`surroundings.kinds.${k}`, { defaultValue: k });

  return (
    <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
      <h3 className="mb-3 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("surroundings.title")}</h3>

      {error ? (
        <p className="text-sm text-paper-500">{t("surroundings.loadError")}</p>
      ) : !data ? (
        <p className="text-sm text-paper-500">{t("common.loading")}</p>
      ) : !data.snapshotAt || !data.areaCovered ? (
        <p className="text-sm text-paper-500">{t("surroundings.notLoaded")}</p>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="mb-1.5 flex items-center gap-2 text-sm font-medium text-ink-900 dark:text-paper-100">
              <MapPin size={15} className="text-teal-600" />
              {t("surroundings.villagesTitle")}
            </p>
            {data.villagesTotal === 0 ? (
              <p className="text-sm text-paper-500">{t("surroundings.none", { km: data.villageRadiusKm })}</p>
            ) : (
              <>
                <p className="text-sm text-paper-700 dark:text-paper-300">
                  {t("surroundings.villageCount", { count: data.villagesTotal, km: data.villageRadiusKm })}
                </p>
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {data.villages.map((v) => (
                    <li key={`${v.name}-${v.distanceKm}`} className="rounded-full bg-paper-100 px-2.5 py-1 text-xs text-paper-700 dark:bg-night-800 dark:text-paper-300">
                      {v.name} · {t("surroundings.km", { km: v.distanceKm })}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          <div>
            <p className="mb-1.5 flex items-center gap-2 text-sm font-medium text-ink-900 dark:text-paper-100">
              <Building2 size={15} className="text-teal-600" />
              {t("surroundings.servicesTitle")}
            </p>
            {data.services.length === 0 ? (
              <p className="text-sm text-paper-500">{t("surroundings.servicesNone", { km: data.serviceRadiusKm })}</p>
            ) : (
              <ul className="divide-y divide-paper-200 dark:divide-night-700">
                {data.services.map((s) => (
                  <li key={`${s.kind}-${s.name}`} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink-800 dark:text-paper-200">{s.name}</span>
                      <span className="block text-xs text-paper-500">
                        {kind(s.kind)} · {t("surroundings.km", { km: s.distanceKm })}
                      </span>
                    </span>
                    {s.phone && (
                      <a
                        href={`tel:${s.phone.replace(/[^+\d]/g, "")}`}
                        className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-paper-200 px-2.5 py-1 text-xs font-medium text-teal-600 hover:bg-paper-50 dark:border-night-700 dark:hover:bg-night-800"
                      >
                        <Phone size={12} />
                        {t("surroundings.call")}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="text-[11px] leading-relaxed text-paper-500">
            {t("surroundings.note", { date: new Date(data.snapshotAt).toLocaleDateString(i18n.language, { day: "numeric", month: "short", year: "numeric" }) })}
          </p>
        </div>
      )}
    </div>
  );
}
