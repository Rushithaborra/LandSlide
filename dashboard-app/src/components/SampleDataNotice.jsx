import { FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * A visible "this is sample data" banner. The profile panel still shows demonstration values because
 * nothing real feeds them yet; without a label they look like live records.
 * `kind` picks the wording under `sample.*` in the language files.
 */
export default function SampleDataNotice({ kind, className = "" }) {
  const { t } = useTranslation();
  return (
    <div
      role="note"
      className={`flex items-start gap-3 rounded-xl border border-risk-moderate/40 bg-risk-moderateSoft px-4 py-3 dark:bg-risk-moderate/10 ${className}`}
    >
      <FlaskConical size={18} className="mt-0.5 shrink-0 text-risk-moderate dark:text-risk-moderateOn" />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-risk-moderate dark:text-risk-moderateOn">{t("sample.title")}</p>
        <p className="mt-0.5 text-sm text-ink-800 dark:text-paper-200">{t(`sample.${kind}`)}</p>
      </div>
    </div>
  );
}
