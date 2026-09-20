import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ScrollText, ShieldCheck } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";

/**
 * DATA SOURCES & METHODOLOGY
 *
 * Surfaces, inside the product, what is real and what is simulated (the same
 * discipline as README.md's "Implemented / Simulated / Pending" section, the
 * `verified_against_primary_text` config flag, and the Broadcast composer's
 * "Simulated" banner): every data source, model and AI feature, honestly labelled.
 *
 * All wording lives in the language files (src/locales/*.json, "methodology"), so
 * it follows the language switcher. Keep it in sync with README.md whenever a
 * source's real/simulated status changes, and re-check the numbers (zone counts,
 * AUC figures) -- they are quoted from the pipeline reports, not computed here.
 */

const BADGE = {
  live: "bg-risk-lowSoft text-risk-low dark:bg-risk-low/10 dark:text-risk-lowOn",
  unverified: "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/10 dark:text-risk-moderateOn",
  derived: "bg-teal-100 text-teal-700 dark:bg-teal-600/20 dark:text-teal-100",
  switchedOff: "bg-risk-highSoft text-risk-high dark:bg-risk-high/10 dark:text-risk-highOn",
  simulated: "bg-paper-100 text-paper-600 dark:bg-night-800 dark:text-paper-400",
};

const STATUS_ORDER = ["live", "unverified", "derived", "switchedOff", "simulated"];

export default function DataMethodology() {
  const { t, i18n } = useTranslation();
  const [filter, setFilter] = useState("all");

  const allSections = useMemo(
    () => t("methodology.sections", { returnObjects: true }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-read when the language changes
    [i18n.language],
  );

  const { counts, total } = useMemo(() => {
    const c = Object.fromEntries(STATUS_ORDER.map((s) => [s, 0]));
    allSections.forEach((s) => s.items.forEach((i) => c[i.status]++));
    return { counts: c, total: Object.values(c).reduce((a, b) => a + b, 0) };
  }, [allSections]);

  const sections = useMemo(() => {
    if (filter === "all") return allSections;
    return allSections.map((s) => ({ ...s, items: s.items.filter((i) => i.status === filter) })).filter((s) => s.items.length > 0);
  }, [filter, allSections]);

  const filters = [
    { id: "all", label: `${t("methodology.all")} (${total})` },
    ...STATUS_ORDER.map((id) => ({ id, label: `${t(`methodology.status.${id}`)} (${counts[id]})` })),
  ];

  return (
    <DashboardLayout title={t("methodology.title")} subtitle={t("methodology.subtitle")}>
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
          <div className="flex items-start gap-3">
            <ScrollText size={20} className="mt-0.5 shrink-0 text-teal-600" />
            <div className="min-w-0 flex-1">
              <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("methodology.whyTitle")}</h2>
              <p className="mt-1 text-sm leading-relaxed text-paper-600 dark:text-paper-400">{t("methodology.whyBody")}</p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {filters.map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  filter === f.id
                    ? "border-teal-600 bg-teal-600 text-white"
                    : "border-paper-200 bg-white text-paper-600 hover:bg-paper-50 dark:border-night-700 dark:bg-night-900 dark:text-paper-400"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {sections.map((section) => (
          <div key={section.title} className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
            <h2 className="mb-3 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{section.title}</h2>
            <div className="divide-y divide-paper-200 dark:divide-night-700">
              {section.items.map((item) => (
                <div key={item.name} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-sm font-medium text-ink-800 dark:text-paper-200">{item.name}</p>
                    <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${BADGE[item.status]}`}>
                      {t(`methodology.status.${item.status}`)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-paper-600 dark:text-paper-400">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="rounded-xl border border-paper-200 bg-paper-50 p-5 dark:border-night-700 dark:bg-night-800">
          <div className="flex items-start gap-3">
            <ShieldCheck size={18} className="mt-0.5 shrink-0 text-paper-500" />
            <p className="text-xs leading-relaxed text-paper-600 dark:text-paper-400">{t("methodology.footer")}</p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
