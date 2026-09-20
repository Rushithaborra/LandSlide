import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDown, Search, LifeBuoy, Phone, Mail, MapPinned } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";

/**
 * HELP CENTRE
 *
 * All wording lives in the language files (src/locales/*.json, under "help"),
 * so it changes with the language switcher like the rest of the dashboard --
 * it used to be hard-coded English here, which is why switching language left
 * the FAQs untouched.
 *
 * Two audiences, one page: a "For everyone" group written in short, plain
 * sentences for residents (many of whom do not read English easily), then the
 * "For officers" groups for people running the dashboard day to day. A filter
 * box searches every question and answer on the page, in the current language.
 */

function Faq({ q, a, query }) {
  return (
    <details className="group border-b border-paper-200 py-3 last:border-0 dark:border-night-700" open={query.length > 1}>
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
        <span className="text-base font-medium text-ink-800 dark:text-paper-200">{q}</span>
        <ChevronDown size={16} className="mt-1 shrink-0 text-paper-500 transition-transform group-open:rotate-180" />
      </summary>
      <p className="mt-2 pr-7 text-base leading-relaxed text-paper-600 dark:text-paper-400">{a}</p>
    </details>
  );
}

export default function HelpDocs() {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState("");
  const allSections = useMemo(
    () => t("help.sections", { returnObjects: true }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-read when the language changes
    [i18n.language],
  );

  // Filter every question and answer on the page as the user types.
  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allSections;
    return allSections
      .map((s) => ({
        ...s,
        faqs: s.faqs.filter((f) => f.q.toLowerCase().includes(q) || f.a.toLowerCase().includes(q) || s.title.toLowerCase().includes(q)),
      }))
      .filter((s) => s.faqs.length > 0);
  }, [query, allSections]);

  const total = allSections.reduce((n, s) => n + s.faqs.length, 0);
  const shown = sections.reduce((n, s) => n + s.faqs.length, 0);

  return (
    <DashboardLayout title={t("help.title")} subtitle={t("help.subtitle")}>
      <div className="mx-auto w-full max-w-3xl space-y-6">
        {/* The two things a frightened or hurried resident needs before anything else. */}
        <div className="space-y-3 rounded-xl border-2 border-risk-high bg-risk-highSoft p-5 dark:bg-risk-high/15">
          <p className="flex items-center gap-2 text-lg font-semibold text-ink-900 dark:text-paper-100">
            <Phone size={20} className="shrink-0 text-risk-high dark:text-risk-highOn" />
            {t("help.emergency")}
          </p>
          <Link
            to="/check-area"
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-base font-medium text-white hover:bg-teal-700"
          >
            <MapPinned size={18} />
            {t("help.checkAreaCta")}
          </Link>
        </div>

        {/* Search within help */}
        <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
          <div className="flex items-start gap-3">
            <LifeBuoy size={20} className="mt-0.5 shrink-0 text-teal-600" />
            <div className="min-w-0 flex-1">
              <h2 className="font-serif text-base font-semibold text-ink-900 dark:text-paper-100">{t("help.howCanWeHelp")}</h2>
              <p className="mt-0.5 text-sm text-paper-600 dark:text-paper-400">{t("help.intro", { total })}</p>
            </div>
          </div>

          <div className="relative mt-4">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("help.searchPlaceholder")}
              aria-label={t("help.searchLabel")}
              className="w-full rounded-lg border border-paper-200 bg-paper-50 py-2.5 pl-9 pr-3 text-base text-paper-700 placeholder:text-paper-500 focus:outline-none focus:ring-2 focus:ring-teal-600/30 dark:border-night-700 dark:bg-night-800 dark:text-paper-300"
            />
          </div>

          {query.trim() && (
            <p className="mt-2 text-sm text-paper-500">
              {shown === 0 ? t("help.noMatch", { query }) : t("help.matchCount", { shown, total, query })}
            </p>
          )}
        </div>

        {/* Question sections, under a heading for who they are for */}
        {sections.map((section, i) => (
          <div key={`${section.group}-${section.title}`} className="space-y-3">
            {(i === 0 || sections[i - 1].group !== section.group) && (
              <h2 className="pt-2 font-serif text-lg font-semibold text-ink-900 dark:text-paper-100">
                {t(section.group === "residents" ? "help.groupResidents" : "help.groupOfficers")}
              </h2>
            )}
            <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
              <h3 className="mb-1 font-serif text-base font-semibold text-ink-900 dark:text-paper-100">{section.title}</h3>
              <p className="mb-2 text-sm text-paper-500">{t("help.clickHint")}</p>
              <div>
                {section.faqs.map((f) => (
                  <Faq key={f.q} q={f.q} a={f.a} query={query.trim()} />
                ))}
              </div>
            </div>
          </div>
        ))}

        {sections.length === 0 && (
          <div className="rounded-xl border border-paper-200 bg-white p-10 text-center dark:border-night-700 dark:bg-night-900">
            <p className="text-base text-paper-600 dark:text-paper-400">{t("help.nothingHere")}</p>
          </div>
        )}

        {/* Still stuck */}
        <div className="rounded-xl border border-paper-200 bg-paper-50 p-5 dark:border-night-700 dark:bg-night-800">
          <h2 className="font-serif text-base font-semibold text-ink-900 dark:text-paper-100">{t("help.stuckTitle")}</h2>
          <p className="mt-1 text-base text-paper-600 dark:text-paper-400">{t("help.stuckBody")}</p>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <span className="flex items-center gap-2 text-paper-700 dark:text-paper-300">
              <Phone size={14} className="text-paper-500" />
              {t("help.controlRoom")}
            </span>
            <span className="flex items-center gap-2 text-paper-700 dark:text-paper-300">
              <Mail size={14} className="text-paper-500" />
              support@ssdma.gov.in
            </span>
          </div>
          <p className="mt-3 text-xs text-paper-500">{t("help.placeholderNote")}</p>
        </div>
      </div>
    </DashboardLayout>
  );
}
