import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Compass } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";

// Without a catch-all route an unknown URL (a typo, or one of the pages removed
// in draft 3 -- /live-map, /settings, /reports -- from an old bookmark) rendered
// a completely blank screen with no way back.
export default function NotFound() {
  const { t } = useTranslation();
  return (
    <DashboardLayout title={t("notFound.title")}>
      <div className="mx-auto max-w-md rounded-xl border border-paper-200 bg-white p-8 text-center dark:border-night-700 dark:bg-night-900">
        <Compass size={32} className="mx-auto text-paper-500" />
        <p className="mt-3 text-base text-paper-600 dark:text-paper-400">{t("notFound.body")}</p>
        <Link
          to="/"
          className="mt-5 inline-block rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800 dark:bg-teal-600 dark:hover:bg-teal-500"
        >
          {t("sidebar.overview")}
        </Link>
      </div>
    </DashboardLayout>
  );
}
