import { useState } from "react";
import { Phone, Trash2, UserPlus, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { getAuthorityContacts, addAuthorityContact, deleteAuthorityContact } from "../services/api";

/**
 * The real call-list app.services.sms_alerts.escalate_critical_alert reads
 * for a "critical" broadcast -- every row here gets an actual phone call
 * (Twilio <Say>) when an officer marks a broadcast Critical. Previously the
 * only way to add a name here was a direct SQL insert (see
 * docs/sms_voice_alert_handover.md); this page is what makes that feature
 * usable without touching the database by hand.
 */
export default function AuthorityContacts() {
  const { t } = useTranslation();
  const { data: contacts, error, retry } = useAsyncData(getAuthorityContacts);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const handleAdd = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await addAuthorityContact({ name, role, phoneNumber });
      setName("");
      setRole("");
      setPhoneNumber("");
      retry();
    } catch (err) {
      setFormError(err.message || "Could not add this contact");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    setDeletingId(id);
    try {
      await deleteAuthorityContact(id);
      retry();
    } catch {
      // leave the row in place -- retry() below still gives a manual out
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <DashboardLayout
      title={t("authorityContacts.title")}
      subtitle={t("authorityContacts.subtitle")}
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900 xl:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-risk-high" />
            <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              {t("authorityContacts.registeredOfficials")}
            </h2>
          </div>

          {error && !contacts ? (
            <LoadError message={error} onRetry={retry} />
          ) : !contacts ? (
            <p className="text-sm text-paper-500">{t("common.loading")}</p>
          ) : contacts.length === 0 ? (
            <p className="text-sm text-paper-500">
              {t("authorityContacts.noneRegistered")}
            </p>
          ) : (
            <div className="divide-y divide-paper-200 dark:divide-night-700">
              {contacts.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink-800 dark:text-paper-200">{c.name}</p>
                    {c.role && <p className="text-xs text-paper-500">{c.role}</p>}
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-paper-600 dark:text-paper-400">
                      <Phone size={13} />
                      {c.phone_number}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDelete(c.id)}
                      disabled={deletingId === c.id}
                      aria-label={t("authorityContacts.removeAriaLabel", { name: c.name })}
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-paper-500 hover:bg-risk-highSoft hover:text-risk-high disabled:opacity-50 dark:hover:bg-risk-high/10"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
          <div className="mb-3 flex items-center gap-2">
            <UserPlus size={16} className="text-ink-800 dark:text-paper-200" />
            <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              {t("authorityContacts.addOfficial")}
            </h2>
          </div>
          <form onSubmit={handleAdd} className="space-y-3">
            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">{t("authorityContacts.name")}</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
                {t("authorityContacts.role")} <span className="normal-case text-paper-400">{t("authorityContacts.optional")}</span>
              </label>
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder={t("authorityContacts.rolePlaceholder")}
                className="mt-1 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
                {t("authorityContacts.phoneNumber")}
              </label>
              <input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                required
                placeholder="+91XXXXXXXXXX"
                className="mt-1 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200"
              />
            </div>

            {formError && <p className="text-sm text-risk-high">{formError}</p>}

            <button
              type="submit"
              disabled={saving}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-800 disabled:opacity-50 dark:bg-teal-600 dark:hover:bg-teal-500"
            >
              <UserPlus size={15} />
              {saving ? t("authorityContacts.adding") : t("authorityContacts.addOfficialButton")}
            </button>
          </form>
          <p className="mt-3 text-xs text-paper-500">
            {t("authorityContacts.twilioNote")}
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
