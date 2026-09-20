import { useEffect, useState } from "react";
import { Lock, LockOpen, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getOfficerAuthMode, getOfficerKey, setOfficerKey, verifyOfficerKey } from "../services/api";

/**
 * Officer sign-in. The backend requires a shared officer key for alerts,
 * citizen reports and authority contacts (see app/security.py); this is where
 * an officer types it. Shown only when the server actually enforces the key,
 * so an open local dev backend has no lock icon. The key stays in this
 * browser tab only (sessionStorage) and is checked against the server before
 * it is saved.
 */
export default function OfficerAccess() {
  const { t } = useTranslation();
  const [mode, setMode] = useState(null); // "enabled" | "disabled" | null while unknown
  const signedIn = Boolean(getOfficerKey());
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [status, setStatus] = useState(null); // null | "checking" | "invalid" | "throttled" | "error"

  useEffect(() => {
    getOfficerAuthMode().then(setMode).catch(() => setMode("disabled"));
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (mode !== "enabled") return null;

  const close = () => {
    setOpen(false);
    setValue("");
    setStatus(null);
  };

  const signIn = async (e) => {
    e.preventDefault();
    const key = value.trim();
    if (!key) return;
    setStatus("checking");
    const result = await verifyOfficerKey(key);
    if (result !== "ok") {
      setStatus(result);
      return;
    }
    setOfficerKey(key);
    // Reload so every page re-fetches with the key (contacts, reports, ...).
    window.location.reload();
  };

  const signOut = () => {
    setOfficerKey("");
    window.location.reload();
  };

  const Icon = signedIn ? LockOpen : Lock;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("officer.button")}
        title={signedIn ? t("officer.signedIn") : t("officer.button")}
        className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium hover:opacity-90 ${
          signedIn
            ? "bg-risk-lowSoft text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn"
            : "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn"
        }`}
      >
        <Icon size={14} />
        <span className="hidden lg:inline">{signedIn ? t("officer.signedIn") : t("officer.button")}</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={close}
          role="presentation"
        >
          <form
            onSubmit={signIn}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label={t("officer.title")}
            className="w-full max-w-sm rounded-xl border border-paper-200 bg-white p-5 shadow-xl dark:border-night-700 dark:bg-night-900"
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-serif text-base font-semibold text-ink-900 dark:text-paper-100">{t("officer.title")}</h2>
              <button type="button" onClick={close} aria-label={t("officer.cancel")} className="text-paper-500 hover:text-ink-900 dark:hover:text-paper-100">
                <X size={16} />
              </button>
            </div>
            <p className="mt-2 text-xs text-paper-600 dark:text-paper-400">{t("officer.body")}</p>

            {!signedIn && (
              <input
                type="password"
                autoFocus
                autoComplete="off"
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                  setStatus(null);
                }}
                placeholder={t("officer.placeholder")}
                aria-label={t("officer.placeholder")}
                className="mt-3 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-900 outline-none focus:border-teal-600 dark:border-night-700 dark:bg-night-800 dark:text-paper-100"
              />
            )}
            {status && status !== "checking" && (
              <p role="alert" className="mt-2 text-xs text-risk-high">
                {t(`officer.${status}`)}
              </p>
            )}

            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={close} className="rounded-lg px-3 py-1.5 text-sm text-paper-700 hover:bg-paper-100 dark:text-paper-300 dark:hover:bg-night-800">
                {t("officer.cancel")}
              </button>
              {signedIn ? (
                <button type="button" onClick={signOut} className="rounded-lg bg-risk-high px-3 py-1.5 text-sm font-medium text-white hover:opacity-90">
                  {t("officer.signOut")}
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!value.trim() || status === "checking"}
                  className="rounded-lg bg-ink-900 px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 dark:bg-teal-600"
                >
                  {status === "checking" ? t("officer.checking") : t("officer.signIn")}
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </>
  );
}
