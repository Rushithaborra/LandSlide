import { useEffect, useState } from "react";
import { X, Pencil, Check, RotateCcw } from "lucide-react";
import { getAdminProfile, updateAdminProfile } from "../services/api";

/**
 * ============================================================================
 *  ADMIN DRAWER  —  side panel with the signed-in officer's details
 *  (NEW IN DRAFT 3)
 * ============================================================================
 * Opens from the avatar in the top bar and slides in from the right.
 * Every field is editable: press "Edit", change the values, press "Save".
 *
 * LINK SPOT J (see src/services/api.js):
 *   getAdminProfile()     -> GET   /api/me
 *   updateAdminProfile()  -> PATCH /api/me
 * Both return mock data today. Nothing in this file changes when they go live.
 * ============================================================================
 */

// Which fields the drawer shows, in order, and how to label them.
const FIELDS = [
  { key: "fullName", label: "Full name" },
  { key: "designation", label: "Designation" },
  { key: "department", label: "Department" },
  { key: "employeeId", label: "Employee ID" },
  { key: "email", label: "Email", type: "email" },
  { key: "phone", label: "Phone", type: "tel" },
  { key: "district", label: "District" },
  { key: "region", label: "Region" },
  { key: "alertChannel", label: "Alert channel" },
];

export default function AdminDrawer({ open, onClose }) {
  const [profile, setProfile] = useState(null);
  const [draft, setDraft] = useState(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getAdminProfile().then((p) => {
      setProfile(p);
      setDraft(p);
    });
  }, []);

  // Escape closes the drawer, like every other side panel on the web.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const setField = (key, value) => setDraft((d) => ({ ...d, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    await updateAdminProfile(draft);
    setProfile(draft);
    setEditing(false);
    setSaving(false);
  };

  const handleCancel = () => {
    setDraft(profile);
    setEditing(false);
  };

  if (!open || !profile) return null;

  const shown = editing ? draft : profile;

  return (
    <>
      {/* Dim the page behind; clicking it closes the drawer */}
      <div
        className="fixed inset-0 z-40 bg-ink-950/40 dark:bg-black/60"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        role="dialog"
        aria-label="Admin details"
        className="fixed right-0 top-0 z-50 h-screen w-full max-w-sm overflow-y-auto border-l border-paper-200 bg-white shadow-xl dark:border-night-700 dark:bg-night-900"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-paper-200 px-5 py-4 dark:border-night-700">
          <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
            Admin details
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close admin details"
            className="flex h-8 w-8 items-center justify-center rounded-full text-paper-600 hover:bg-paper-100 dark:text-paper-400 dark:hover:bg-night-800"
          >
            <X size={17} />
          </button>
        </div>

        {/* Identity block */}
        <div className="flex items-center gap-3 border-b border-paper-200 px-5 py-4 dark:border-night-700">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-ink-900 text-sm font-semibold text-white dark:bg-teal-600">
            {profile.initials}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-900 dark:text-paper-100">
              {shown.fullName}
            </p>
            <p className="truncate text-xs text-paper-600 dark:text-paper-400">
              {shown.designation}
            </p>
          </div>
        </div>

        {/* Fields */}
        <div className="space-y-3 px-5 py-4">
          {FIELDS.map(({ key, label, type }) => (
            <div key={key}>
              <label
                htmlFor={`admin-${key}`}
                className="text-[11px] font-medium uppercase tracking-wide text-paper-500"
              >
                {label}
              </label>
              {editing ? (
                <input
                  id={`admin-${key}`}
                  type={type || "text"}
                  value={shown[key] || ""}
                  onChange={(e) => setField(key, e.target.value)}
                  className="mt-1 w-full rounded-lg border border-paper-200 bg-paper-50 px-3 py-2 text-sm text-paper-700 dark:text-paper-300 focus:outline-none focus:ring-2 focus:ring-teal-600/30 dark:border-night-700 dark:bg-night-800"
                />
              ) : (
                <p className="mt-0.5 text-sm text-paper-700 dark:text-paper-300">
                  {shown[key]}
                </p>
              )}
            </div>
          ))}

          <div className="pt-1">
            <p className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
              Last login
            </p>
            <p className="mt-0.5 text-sm text-paper-600 dark:text-paper-400">
              {profile.lastLogin}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 flex gap-2 border-t border-paper-200 bg-white px-5 py-4 dark:border-night-700 dark:bg-night-900">
          {editing ? (
            <>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-ink-900 py-2 text-sm font-medium text-white hover:bg-ink-800 disabled:opacity-50 dark:bg-teal-600 dark:hover:bg-teal-500"
              >
                <Check size={15} />
                {saving ? "Saving…" : "Save changes"}
              </button>
              <button
                type="button"
                onClick={handleCancel}
                className="flex items-center justify-center gap-1.5 rounded-lg border border-paper-200 px-3 py-2 text-sm font-medium text-paper-700 hover:bg-paper-100 dark:border-night-700 dark:text-paper-300 dark:hover:bg-night-800"
              >
                <RotateCcw size={15} />
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-paper-200 py-2 text-sm font-medium text-paper-700 hover:bg-paper-100 dark:border-night-700 dark:text-paper-300 dark:hover:bg-night-800"
            >
              <Pencil size={15} />
              Edit details
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
