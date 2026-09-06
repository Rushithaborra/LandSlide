import { useMemo, useState } from "react";
import { ChevronDown, Search, LifeBuoy, Phone, Mail } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";

/**
 * ============================================================================
 *  HELP CENTRE
 * ============================================================================
 * A self-service hub for the officers who USE this dashboard day to day, so
 * they can answer their own questions without ringing the technical team.
 *
 * DRAFT 6: the questions were rewritten from the point of view of a district
 * officer working with the live system — reading the map, acting on an alert,
 * verifying a citizen report, filing records, and what to do when something
 * looks wrong. The earlier build-status questions were removed; they belonged
 * to the development phase, not to a deployed product.
 *
 * A filter box at the top searches every question and answer on this page.
 * ============================================================================
 */

const SECTIONS = [
  {
    title: "Everyday use",
    faqs: [
      {
        q: "What am I supposed to check first thing in the morning?",
        a: "Open the Overview page. Read the five cards across the top, then the map, then the Active Alerts panel. If High Risk Zones or Active Alerts has gone up since yesterday, the card says so underneath the number. That takes about a minute and tells you whether today is a normal day or not.",
      },
      {
        q: "How do I find one particular village, alert or incident quickly?",
        a: "Use the search box at the top of any page, or press Ctrl+K (Cmd+K on a Mac). Type part of the name and results appear grouped by type. Press Enter on the one you want.",
      },
      {
        q: "How often does the information on screen change?",
        a: "The scrolling warning strip refreshes itself every five minutes. Everything else loads fresh each time you open or switch to a page. If you have had a page open for a while, switch away and back, or refresh the browser, to be sure you are looking at the latest.",
      },
      {
        q: "Can I use this on a phone or tablet?",
        a: "Yes on a tablet — the layout adjusts. On a small phone screen the side menu is hidden and the dashboard is cramped; it is meant for a desk or a control-room display. Field staff should use the citizen reporting app instead.",
      },
      {
        q: "The screen is too bright at night in the control room.",
        a: "Use the sun or moon button in the top bar, between the bell and your name. It switches the whole dashboard to a dark theme, and it remembers your choice on that computer.",
      },
      {
        q: "Can I leave this open on a wall display all day?",
        a: "Yes. The Overview page is designed for it. Keep in mind it does not refresh on its own except for the warning strip, so someone should refresh the browser at the start of each shift.",
      },
    ],
  },
  {
    title: "Reading the risk map",
    faqs: [
      {
        q: "What do the coloured circles on the map mean?",
        a: "Each circle is one monitored zone. The colour is its current risk level — terracotta for High, turmeric for Moderate, moss green for Low. The size of the circle is how landslide-prone that terrain is, so a big red circle is the most serious combination.",
      },
      {
        q: "What is 'susceptibility', and how is it different from risk?",
        a: "Susceptibility is how prone a place is because of its terrain alone — slope, soil, past landslides — and it barely changes from month to month. Risk is susceptibility combined with today's rainfall. A steep slope has high susceptibility all year, but it only becomes High risk when it is raining hard.",
      },
      {
        q: "Why did a zone change from Moderate to High without any new rain reported?",
        a: "The trigger is cumulative rainfall, not just the last hour. Several days of steady rain can push a zone over the 48-hour threshold even when today looks calm. Open the rainfall chart on the Overview page to see the build-up.",
      },
      {
        q: "What does the 100 mm dashed line on the rainfall chart mean?",
        a: "It is the rainfall level above which the system treats conditions as dangerous for this region. Bars crossing that line are the days that push zones towards a High rating.",
      },
      {
        q: "A village I know is at risk is not shown on the map. Why?",
        a: "Only zones that have been surveyed and added to the system appear. Raise it with your state disaster management authority — new zones are added upstream, not from this dashboard.",
      },
      {
        q: "Can I zoom in to street level?",
        a: "You can zoom the map with the + and − buttons or the scroll wheel. The risk zones stay at the same scale they were assessed at, so zooming in shows you more roads and rivers, not finer risk detail.",
      },
    ],
  },
  {
    title: "Alerts and warnings",
    faqs: [
      {
        q: "An alert has just appeared. What am I expected to do?",
        a: "Read the location and severity, check that zone on the map, then follow your district's standard operating procedure for that severity. This dashboard tells you what the system has detected; the decision to evacuate or close a road is yours.",
      },
      {
        q: "Does the public get warned automatically, or do I have to do it?",
        a: "Automatically. When a zone turns High, the system sends SMS warnings to registered numbers in that area without waiting for anyone to press a button. Your job is to act on the ground, not to send the message.",
      },
      {
        q: "Who exactly receives those SMS messages?",
        a: "Numbers registered against the affected area in the alert system. If a village is not receiving warnings, its numbers are missing from that list — raise it with the team who maintain the alert dispatch service.",
      },
      {
        q: "Where does the scrolling text at the top of the screen come from?",
        a: "It is generated by the system — either from an alert the risk engine has just raised, or from the India Meteorological Department bulletin for this region. Nobody types it in. Hover over it to stop it scrolling so you can read a long one.",
      },
      {
        q: "An alert is showing but the weather here is fine. Is it wrong?",
        a: "Not necessarily. Alerts are raised for the zone, which may be several kilometres away and higher up. Check the location on the alert before assuming it is a false alarm. If the location really is where you are and conditions are clearly calm, note it and report it — those notes are what improve the model.",
      },
      {
        q: "A landslide happened but no alert was raised. What now?",
        a: "Record it on the Incidents page through your usual reporting line, and flag it to the technical team. Events the system missed are the most valuable training data it can get.",
      },
      {
        q: "What is the difference between the Alerts page and the notification bell?",
        a: "The Alerts page is the full log of everything that has been raised. The bell is your personal unread list — the things raised since you last looked.",
      },
    ],
  },
  {
    title: "Citizen reports and verification",
    faqs: [
      {
        q: "Where do citizen reports come from?",
        a: "Residents submit them from the public reporting app on their phone, with a photo and a note. They arrive here on the Citizen Reports page, marked 'Pending verification'.",
      },
      {
        q: "How do I verify a report?",
        a: "Click the report to open it. You get the photo, the exact location and coordinates, the landmark, the time it was sent, the weather at that moment, and the reporter's details. Once you have checked the site — in person or against the risk map — press 'Verify report' at the bottom right. The report is then marked Verified for everyone.",
      },
      {
        q: "What does 'Verified' actually mean?",
        a: "That an officer has confirmed the report describes something real. It does not mean the danger has been dealt with, and it does not create an incident record. Verified reports feed into the model as ground truth.",
      },
      {
        q: "Can I undo a verification if I made a mistake?",
        a: "Not from this screen. Contact the technical team to reverse it. This is deliberate — verification is an official act and should not be casually toggled.",
      },
      {
        q: "A report looks like a false alarm or a prank. What do I do?",
        a: "Leave it as Pending. Do not verify it. Persistent false reporting from one number should be raised with the team who run the reporting app.",
      },
      {
        q: "Is the reporter's phone number confidential?",
        a: "It is visible to officers with dashboard access so you can call back for details. It is not shown publicly — the list shows submissions as 'Anonymous'. Treat the number as official information and do not share it outside your office.",
      },
      {
        q: "Does verifying a report warn anyone?",
        a: "No. Verification is a record-keeping and quality action. Warnings are raised by the risk engine from rainfall and terrain data, separately.",
      },
    ],
  },
  {
    title: "Records and reports",
    faqs: [
      {
        q: "How do I get a report for a meeting or a file?",
        a: "Go to the Incidents page and press 'Download' on that incident's row. A PDF is produced immediately.",
      },
      {
        q: "What is inside that PDF?",
        a: "The incident's ID, location, area, date, severity and status, casualties and infrastructure impact, the weather report for the event, the rainfall trend in the days before it, previous recorded landslide activity in that area, the response summary, and every citizen report filed from the same area.",
      },
      {
        q: "Can I download a report covering a whole month rather than one incident?",
        a: "Not yet. Reports are per incident today. A date-range summary is a sensible next request to put to the technical team.",
      },
      {
        q: "What is the difference between an Alert and an Incident?",
        a: "An alert is a warning before something happens. An incident is the record of a landslide that actually happened, written after field verification. Not every alert becomes an incident, and that is the system working correctly.",
      },
      {
        q: "Can I add or edit an incident from this dashboard?",
        a: "No. Incidents are entered through the field verification process and this dashboard displays them. This keeps one authoritative record rather than two that disagree.",
      },
    ],
  },
  {
    title: "When something looks wrong",
    faqs: [
      {
        q: "The numbers have not changed all day. Is the system stuck?",
        a: "First refresh the browser. If they still have not moved, open Data & Observations and look at the sync times. A feed that last synced hours ago is the likely cause.",
      },
      {
        q: "What does the Data & Observations page tell me?",
        a: "Whether each upstream source — IMD rainfall, Open-Meteo, the GSI landslide inventory, satellite imagery, the SMS gateway — is connected, and when it last sent data. It is the first place to look when something seems stale.",
      },
      {
        q: "A data source says 'Not connected'. Should I stop trusting the dashboard?",
        a: "Depends which one. If a rainfall feed is down, risk levels may be out of date and you should treat them with caution and rely on local observation. If the SMS gateway is down, warnings may not be reaching citizens — escalate that immediately.",
      },
      {
        q: "'System Health' shows less than 100%. What does that mean?",
        a: "One or more data feeds did not respond in time. It is a warning that some information may be stale, not that the system has failed. Check Data & Observations for which one.",
      },
      {
        q: "The map area is blank or grey.",
        a: "The map background is loaded from the internet. A blank map usually means this computer has lost its connection, or a firewall is blocking it. The risk circles and all other data still work.",
      },
      {
        q: "Who do I contact when something is genuinely broken?",
        a: "Your state disaster management authority's technical contact. Tell them what page you were on, what you expected, what you saw, and the time — that is usually enough to diagnose it.",
      },
    ],
  },
  {
    title: "Account and access",
    faqs: [
      {
        q: "How do I update my own contact details?",
        a: "Click your name or initials at the top right. A panel opens with your designation, department, employee ID, phone, email, district and alert channel. Press 'Edit details', change what you need, then 'Save changes'.",
      },
      {
        q: "Why does it matter that my details are correct?",
        a: "Your alert channel and phone number decide how the system reaches you when a High alert is raised outside office hours.",
      },
      {
        q: "Can I see districts other than my own?",
        a: "The dashboard shows the region assigned to your office. If you need a neighbouring district — during a joint operation, for example — ask your state authority to widen your access.",
      },
      {
        q: "Someone else needs access. How do they get an account?",
        a: "Accounts are issued by your state disaster management authority, not from inside this dashboard. Do not share your own login.",
      },
      {
        q: "Is it safe to leave the dashboard open when I step away?",
        a: "Lock your computer. The dashboard shows citizens' names and phone numbers, so treat the screen the way you would treat an open case file.",
      },
    ],
  },
];

function Faq({ q, a, query }) {
  return (
    <details
      className="group border-b border-paper-200 py-3 last:border-0 dark:border-night-700"
      open={query.length > 1}
    >
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
        <span className="text-sm font-medium text-ink-800 dark:text-paper-200">
          {q}
        </span>
        <ChevronDown
          size={16}
          className="mt-0.5 shrink-0 text-paper-500 transition-transform group-open:rotate-180"
        />
      </summary>
      <p className="mt-2 pr-7 text-sm leading-relaxed text-paper-600 dark:text-paper-400">
        {a}
      </p>
    </details>
  );
}

export default function HelpDocs() {
  const [query, setQuery] = useState("");

  // Filter every question and answer on the page as the officer types.
  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return SECTIONS;
    return SECTIONS.map((s) => ({
      ...s,
      faqs: s.faqs.filter(
        (f) =>
          f.q.toLowerCase().includes(q) ||
          f.a.toLowerCase().includes(q) ||
          s.title.toLowerCase().includes(q)
      ),
    })).filter((s) => s.faqs.length > 0);
  }, [query]);

  const total = SECTIONS.reduce((n, s) => n + s.faqs.length, 0);
  const shown = sections.reduce((n, s) => n + s.faqs.length, 0);

  return (
    <DashboardLayout
      title="Help"
      subtitle="Answers to the questions officers ask most often"
    >
      <div className="mx-auto w-full max-w-3xl space-y-6">
        {/* Search within help */}
        <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
          <div className="flex items-start gap-3">
            <LifeBuoy size={20} className="mt-0.5 shrink-0 text-teal-600" />
            <div className="min-w-0 flex-1">
              <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
                How can we help?
              </h2>
              <p className="mt-0.5 text-xs text-paper-600 dark:text-paper-400">
                {total} answers covering daily use, the risk map, alerts,
                citizen reports, records and troubleshooting.
              </p>
            </div>
          </div>

          <div className="relative mt-4">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper-500"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search help — try 'alert', 'verify', 'rainfall'…"
              aria-label="Search the help centre"
              className="w-full rounded-lg border border-paper-200 bg-paper-50 py-2 pl-9 pr-3 text-sm text-paper-700 placeholder:text-paper-500 focus:outline-none focus:ring-2 focus:ring-teal-600/30 dark:border-night-700 dark:bg-night-800 dark:text-paper-300"
            />
          </div>

          {query.trim() && (
            <p className="mt-2 text-xs text-paper-500">
              {shown === 0
                ? `No answers matched “${query}”.`
                : `${shown} of ${total} answers match “${query}”.`}
            </p>
          )}
        </div>

        {/* Question sections */}
        {sections.map((section) => (
          <div
            key={section.title}
            className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900"
          >
            <h2 className="mb-1 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              {section.title}
            </h2>
            <p className="mb-2 text-xs text-paper-500">
              Click a question to open the answer
            </p>
            <div>
              {section.faqs.map((f) => (
                <Faq key={f.q} q={f.q} a={f.a} query={query.trim()} />
              ))}
            </div>
          </div>
        ))}

        {sections.length === 0 && (
          <div className="rounded-xl border border-paper-200 bg-white p-10 text-center dark:border-night-700 dark:bg-night-900">
            <p className="text-sm text-paper-600 dark:text-paper-400">
              Nothing here matches that. Try a shorter word, or contact your
              state technical support below.
            </p>
          </div>
        )}

        {/* Still stuck */}
        <div className="rounded-xl border border-paper-200 bg-paper-50 p-5 dark:border-night-700 dark:bg-night-800">
          <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
            Still stuck?
          </h2>
          <p className="mt-1 text-sm text-paper-600 dark:text-paper-400">
            Contact your state disaster management authority's technical desk.
            Tell them which page you were on, what you expected, what you saw,
            and the time — that is usually enough to diagnose it.
          </p>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <span className="flex items-center gap-2 text-paper-700 dark:text-paper-300">
              <Phone size={14} className="text-paper-500" />
              State control room · 1077
            </span>
            <span className="flex items-center gap-2 text-paper-700 dark:text-paper-300">
              <Mail size={14} className="text-paper-500" />
              support@ssdma.gov.in
            </span>
          </div>
          <p className="mt-3 text-[11px] text-paper-500">
            Placeholder contact details — replace with your office's real
            support desk before deployment.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
