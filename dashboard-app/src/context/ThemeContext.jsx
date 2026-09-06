import { createContext, useContext, useEffect, useState } from "react";

/**
 * ============================================================================
 *  THEME CONTEXT  —  light / dark switch (NEW IN DRAFT 3)
 * ============================================================================
 * How it works, in one line: this adds or removes the CSS class "dark" on the
 * <html> element, and Tailwind's `dark:` variants do the rest.
 *
 *   light  ->  <html>            -> every original class applies unchanged
 *   dark   ->  <html class="dark"> -> the `dark:` classes take over
 *
 * The choice is remembered in the browser's localStorage, so refreshing the
 * page keeps the theme. If the user has never chosen, we follow whatever
 * their operating system is set to.
 *
 * Light mode is IDENTICAL to draft 2 — no light-mode class was changed.
 * ============================================================================
 */

const ThemeContext = createContext({ theme: "light", toggleTheme: () => {} });

const STORAGE_KEY = "sih-theme";

function getInitialTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // localStorage can throw in private mode — fall through to the OS setting
  }
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // ignore — the theme still works for this session
    }
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// The hook lives next to its provider on purpose; this file exports both.
// eslint-disable-next-line react/only-export-components
export function useTheme() {
  return useContext(ThemeContext);
}
