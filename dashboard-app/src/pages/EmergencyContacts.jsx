import { useEffect, useState } from "react";
import { Phone } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import { getEmergencyContacts } from "../services/api";

/**
 * Real public helpline numbers, click-to-call. A static directory, not
 * synced live against any government system -- 112/108 are real and
 * unambiguous; anything state/agency-specific is honestly marked
 * unconfirmed rather than presented as verified (see mockData.js).
 */
export default function EmergencyContacts() {
  const [contacts, setContacts] = useState([]);

  useEffect(() => {
    getEmergencyContacts().then(setContacts);
  }, []);

  return (
    <DashboardLayout title="Emergency Contacts" subtitle="Click-to-call directory for disaster response">
      <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 divide-y divide-paper-200 dark:divide-night-700">
        {contacts.map((c) => (
          <div key={c.name} className="flex items-center justify-between py-3 gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink-800 dark:text-paper-200">{c.name}</p>
              <p className="text-xs text-paper-500">{c.jurisdiction}</p>
              {!c.verified && (
                <span className="mt-1 inline-block text-[11px] font-medium px-2 py-0.5 rounded-full bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn">
                  Unconfirmed — verify before real-world use
                </span>
              )}
            </div>
            {c.verified ? (
              <a
                href={`tel:${c.phone}`}
                className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg bg-risk-high px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
              >
                <Phone size={14} />
                Call {c.phone}
              </a>
            ) : (
              <span className="shrink-0 whitespace-nowrap text-xs text-paper-500">{c.phone}</span>
            )}
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
