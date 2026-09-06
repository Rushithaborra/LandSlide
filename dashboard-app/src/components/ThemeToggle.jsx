import { Sun, Moon } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

/**
 * Light / dark theme switch (NEW IN DRAFT 3).
 * Sits in the top bar, to the RIGHT of the notification bell and to the
 * LEFT of the admin avatar.
 *
 * Light mode is the original look, unchanged. Dark mode is driven entirely by
 * Tailwind `dark:` classes — see src/context/ThemeContext.jsx.
 */
export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-paper-100 dark:hover:bg-night-800"
    >
      {isDark ? (
        <Sun size={18} className="text-paper-300" />
      ) : (
        <Moon size={18} className="text-paper-600 dark:text-paper-400" />
      )}
    </button>
  );
}
