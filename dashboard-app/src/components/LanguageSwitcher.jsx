import { Globe } from "lucide-react";
import { useTranslation } from "react-i18next";

// Sits in the Topbar next to ThemeToggle, same compact-control pattern.
// Choice persists across reloads via localStorage (read by src/i18n.js on init).
const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "ne", label: "नेपाली" },
];

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation();

  const handleChange = (e) => {
    const lng = e.target.value;
    i18n.changeLanguage(lng);
    localStorage.setItem("language", lng);
  };

  return (
    <div className="flex items-center gap-1 rounded-lg px-1.5 py-1 hover:bg-paper-100 dark:hover:bg-night-800">
      <Globe size={16} className="text-paper-500 dark:text-paper-400" />
      <select
        value={i18n.language}
        onChange={handleChange}
        aria-label={t("topbar.changeLanguage")}
        className="bg-transparent text-xs font-medium text-paper-700 focus:outline-none dark:text-paper-300 [&>option]:text-ink-900"
      >
        {LANGUAGES.map(({ code, label }) => (
          <option key={code} value={code}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );
}
