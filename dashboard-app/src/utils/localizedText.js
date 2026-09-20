// Alert wording and relative times in the viewer's language.
//
// These used to be built as English strings when data was fetched (api.js), so
// switching language left them in English -- and stale until the next fetch.
// Components now format them at render time from the raw values instead.

// Dispatched on window when the live alert stream reports a new alert, so several
// components can refresh from one connection.
export const ALERTS_CHANGED_EVENT = "alerts-changed";

// The one sentence the backend writes when it raises an alert
// (app/services/alert_engine.py check_and_trigger). It is stored as text, so it is
// taken apart here rather than migrating old rows. Anything that doesn't match
// (a future wording change) is shown as-is -- untranslated, never dropped or mangled.
const ALERT_SENTENCE =
  /^(\w+) landslide-risk zone — (\d+)d rainfall averaged ([\d.]+)mm\/day, exceeding the ([\d.]+)mm\/day danger threshold for this susceptibility level$/;

/**
 * @param {string} text the backend's alert sentence
 * @param {(key: string, opts?: object) => string} t i18next translate function
 * @param {{ short?: boolean }} opts short = only the rainfall part (the strip already
 *   tags the risk level separately)
 */
export function alertSentence(text, t, { short = false } = {}) {
  const m = ALERT_SENTENCE.exec(text || "");
  if (!m) return text;
  const [, tier, days, mean, threshold] = m;
  const rain = t("alertText.rain", { days, mean, threshold });
  return short ? rain : t("alertText.full", { tier: t(`alertText.tier.${tier.toLowerCase()}`, { defaultValue: tier }), rain });
}

// Relative times come from the language files ("ago.*"), not the browser's Intl
// data: some browsers ship no Nepali relative-time data and silently fall back to
// English, which is exactly the bug being fixed.

/** "6 days ago" / "6 दिन पहले" from a number of minutes. */
export function agoFromMinutes(minutes, t) {
  if (minutes < 1) return t("ago.now");
  if (minutes < 60) return t("ago.minutes", { count: Math.round(minutes) });
  const hours = Math.round(minutes / 60);
  if (hours < 24) return t("ago.hours", { count: hours });
  return t("ago.days", { count: Math.round(hours / 24) });
}

export function agoLabel(iso, t) {
  return agoFromMinutes((Date.now() - new Date(iso).getTime()) / 60000, t);
}

/** "today" / "yesterday" / "Sep 19" for a daily-rainfall date (stored per UTC day). */
export function dayWord(isoDay, t, lang) {
  const utcDay = (d) => Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  const diff = Math.round((utcDay(new Date(isoDay)) - utcDay(new Date())) / 86400000);
  if (diff === 0) return t("ago.today");
  if (diff === -1) return t("ago.yesterday");
  return new Date(isoDay).toLocaleDateString(lang, { month: "short", day: "numeric", timeZone: "UTC" });
}
